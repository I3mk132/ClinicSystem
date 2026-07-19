from datetime import datetime

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, hash_api_key
from app.models.api_key import ApiKey
from app.models.clinic import Clinic
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_exception

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires administrator privileges",
        )
    return current_user


def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """The global developer account (manages clinics, not clinic data)."""
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires superadmin privileges",
        )
    return current_user


def get_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    """
    Guards the /api/v1/public/* routes used by external integrations
    (main hospital system, WhatsApp/Telegram bots, ...). See
    routers/api_keys.py for how admins issue these keys.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key = db.query(ApiKey).filter(ApiKey.hashed_key == hash_api_key(x_api_key)).first()
    if not key or not key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    key.last_used_at = datetime.utcnow()
    db.commit()
    return key


# --- Multi-tenant resolution (Session 2a) -----------------------------------
#
# Every request must be resolved to exactly one clinic (tenant). There are two
# resolution paths, and they must never be mixed:
#   - Web portal + public header endpoints: the caller tells us which clinic via
#     the X-Clinic header (the clinic slug, sent by the frontend), with a
#     fallback of matching the request host/origin against a clinic custom_domain.
#   - API-key endpoints (/api/v1/public/*): the tenant is whatever clinic OWNS
#     the API key (get_api_key_clinic). Headers are ignored there so a key can
#     never be pointed at another clinic's data.
#
# NOTE (Session 2b): these dependencies exist and resolve correctly, but the
# routers do not yet FILTER their queries by the resolved clinic. Wiring
# get_current_clinic / get_api_key_clinic into every router + services.py (the
# cross-tenant isolation audit) is Session 2b.


def _host_only(value: str | None) -> str | None:
    """Strip scheme and any :port from an Origin/Host header, lowercased."""
    if not value:
        return None
    host = value.strip().lower()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    host = host.split(":", 1)[0]
    return host or None


def _resolve_clinic(x_clinic: str | None, origin: str | None, host: str | None, db: Session) -> Clinic | None:
    """Look up a clinic from the X-Clinic slug, falling back to host/Origin -> custom_domain.

    Returns None if nothing matches. Raises 403 if a clinic is found but inactive
    (an inactive tenant must not serve requests either way).
    """
    clinic: Clinic | None = None
    if x_clinic:
        clinic = db.query(Clinic).filter(Clinic.slug == x_clinic.strip().lower()).first()
    if clinic is None:
        candidate = _host_only(origin) or _host_only(host)
        if candidate:
            clinic = db.query(Clinic).filter(Clinic.custom_domain == candidate).first()
    if clinic is not None and not clinic.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This clinic is not active",
        )
    return clinic


def get_current_clinic(
    x_clinic: str | None = Header(default=None, alias="X-Clinic"),
    origin: str | None = Header(default=None),
    host: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Clinic:
    """
    Resolve the tenant for a web-portal / header-based request (required).

    Priority: X-Clinic slug, then request Origin/Host matched against a clinic's
    custom_domain. Raises 400 if no clinic can be resolved, 403 if it's inactive.
    """
    clinic = _resolve_clinic(x_clinic, origin, host, db)
    if clinic is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve clinic - missing or unknown X-Clinic header",
        )
    return clinic


def get_current_clinic_optional(
    x_clinic: str | None = Header(default=None, alias="X-Clinic"),
    origin: str | None = Header(default=None),
    host: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Clinic | None:
    """Like get_current_clinic but returns None instead of 400 when unresolved.

    Used by /auth/login, where a SUPERADMIN (clinic_id NULL) logs in without any
    X-Clinic header while regular users still resolve to their clinic.
    """
    return _resolve_clinic(x_clinic, origin, host, db)


def get_api_key_clinic(
    key: ApiKey = Depends(get_api_key),
    db: Session = Depends(get_db),
) -> Clinic:
    """Resolve the tenant that OWNS the presented API key (headers ignored)."""
    clinic = db.query(Clinic).filter(Clinic.id == key.clinic_id).first()
    if clinic is None or not clinic.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is not associated with an active clinic",
        )
    return clinic
