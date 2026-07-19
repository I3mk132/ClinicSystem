import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import ContactMethod


class VerificationPurpose(str, enum.Enum):
    # ACCOUNT_VERIFY is no longer issued (signup OTP was removed) but stays
    # declared so existing rows in older databases still deserialize.
    ACCOUNT_VERIFY = "account_verify"
    PASSWORD_RESET = "password_reset"


class VerificationCode(Base):
    """
    A short-lived one-time code sent by email or SMS (see app/notifications.py).
    Used for both "verify my new account" and "forgot password" flows so the
    two features share one expiry/consumption mechanism.

    The code itself is stored hashed (same as passwords) - never in plain
    text - so a leaked database doesn't hand out valid codes.
    """

    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Tenant owner (denormalized from user for direct filtering).
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    purpose: Mapped[VerificationPurpose] = mapped_column(Enum(VerificationPurpose), nullable=False)
    channel: Mapped[ContactMethod] = mapped_column(Enum(ContactMethod), nullable=False)

    hashed_code: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    # Failed guesses so far - the code is rejected once MAX_OTP_ATTEMPTS is
    # reached, so a 6-digit code can't be brute-forced within its lifetime.
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
