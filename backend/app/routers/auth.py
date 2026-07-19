from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    generate_otp_code,
    hash_code,
    hash_password,
    verify_code,
    verify_password,
)
from app.dependencies import get_current_clinic, get_current_clinic_optional, get_current_user
from app.models.clinic import Clinic
from app.models.user import ContactMethod, User, UserRole
from app.models.verification import VerificationCode, VerificationPurpose
from app.notifications import send_otp
from app.schemas.token import LoginRequest, Token
from app.schemas.user import UserCreate, UserOut
from app.schemas.verification import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# A code is rejected outright after this many wrong guesses (the user must
# request a fresh one), so short numeric OTPs can't be brute-forced.
MAX_OTP_ATTEMPTS = 5


def _consume_code(db: Session, user: User, purpose: VerificationPurpose, plain_code: str) -> None:
    """Validate the latest unused OTP for (user, purpose) and mark it used.

    Raises 400 on any failure. Every wrong guess is counted and committed, so
    attackers can't retry a code indefinitely within its expiry window.
    """
    code_entry = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.clinic_id == user.clinic_id,
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == purpose,
            VerificationCode.is_used.is_(False),
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    if not code_entry or code_entry.expires_at < datetime.utcnow():
        raise invalid
    if code_entry.attempts >= MAX_OTP_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many incorrect attempts - request a new code",
        )
    if not verify_code(plain_code, code_entry.hashed_code):
        code_entry.attempts += 1
        db.commit()
        raise invalid

    code_entry.is_used = True


def _issue_code(db: Session, user: User, purpose: VerificationPurpose) -> str:
    """Create+store a new OTP for the user and send it over their chosen contact_method."""
    code = generate_otp_code(settings.OTP_LENGTH)
    db.add(
        VerificationCode(
            clinic_id=user.clinic_id,
            user_id=user.id,
            purpose=purpose,
            channel=user.contact_method,
            hashed_code=hash_code(code),
            expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        )
    )
    db.commit()

    destination = user.email if user.contact_method == ContactMethod.EMAIL else user.phone
    send_otp(user.contact_method.value, destination, code, purpose.value, lang=user.preferred_language)
    return code


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    # Emails are stored (and looked up) lowercased so "User@x.com" and
    # "user@x.com" can't become two different accounts. Uniqueness is PER clinic.
    email = payload.email.lower() if payload.email else None
    if email and db.query(User).filter(User.clinic_id == clinic.id, User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    if payload.phone and db.query(User).filter(User.clinic_id == clinic.id, User.phone == payload.phone).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this phone number already exists")

    user = User(
        clinic_id=clinic.id,
        full_name=payload.full_name,
        email=email,
        phone=payload.phone,
        preferred_language=payload.preferred_language,
        contact_method=payload.contact_method,
        hashed_password=hash_password(payload.password),
        role=UserRole.PATIENT,
        # Accounts are active immediately - no signup OTP. Verification codes
        # are only used for the forgot/reset-password flow now.
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(
    payload: LoginRequest,
    clinic: Clinic | None = Depends(get_current_clinic_optional),
    db: Session = Depends(get_db),
):
    identifier = payload.identifier.strip().lower()  # email lookups are case-insensitive; harmless for phone numbers
    match = (User.email == identifier) | (User.phone == identifier)

    # Regular users are scoped to the resolved clinic (the same email can exist
    # in more than one clinic). SUPERADMIN is global (clinic_id NULL) and logs in
    # with no X-Clinic header, so fall back to a global superadmin lookup.
    user = None
    if clinic is not None:
        user = db.query(User).filter(User.clinic_id == clinic.id, match).first()
    if user is None:
        user = (
            db.query(User)
            .filter(User.role == UserRole.SUPERADMIN, User.clinic_id.is_(None), match)
            .first()
        )
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email/phone or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled")

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Forgot password (code sent to whichever contact_method the user signed up with)
# ---------------------------------------------------------------------------
@router.post("/password/forgot", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    identifier = payload.identifier.strip().lower()  # email lookups are case-insensitive; harmless for phone numbers
    user = (
        db.query(User)
        .filter(User.clinic_id == clinic.id, (User.email == identifier) | (User.phone == identifier))
        .first()
    )

    # Always return the same generic message, whether or not an account was
    # found, so this endpoint can't be used to check which emails/phones
    # are registered.
    generic_message = MessageResponse(detail="If an account exists, a reset code has been sent")
    if not user or not user.is_active:
        return generic_message

    _issue_code(db, user, VerificationPurpose.PASSWORD_RESET)
    return generic_message


@router.post("/password/reset", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    identifier = payload.identifier.strip().lower()  # email lookups are case-insensitive; harmless for phone numbers
    user = (
        db.query(User)
        .filter(User.clinic_id == clinic.id, (User.email == identifier) | (User.phone == identifier))
        .first()
    )
    # Same 400 message whether the identifier is unknown or the code is wrong,
    # so this endpoint can't be used to probe which accounts exist.
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    _consume_code(db, user, VerificationPurpose.PASSWORD_RESET, payload.code)
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(detail="Password has been reset - you can now log in")
