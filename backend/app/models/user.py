import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    PATIENT = "patient"
    ADMIN = "admin"


class ContactMethod(str, enum.Enum):
    """Which channel a user's verification / password-reset codes are sent to."""

    EMAIL = "email"
    PHONE = "phone"


class User(Base):
    """
    A person who can log into the portal.
    Patients register themselves; admins are created via the seed script
    or promoted by another admin.

    `email` and `phone` are both optional at the database level (a patient
    booked in by a WhatsApp/Telegram bot via the public API may only have a
    phone number - see routers/public.py), but the app enforces that at
    least one of them is present, and that `contact_method` points at a
    channel that was actually provided (see schemas/user.py).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Tenant this row belongs to. Nullable during the Session 2 split; Session 2b
    # flips it to NOT NULL and makes email/phone unique per-clinic instead of global.
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=True)
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.PATIENT, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(5), default="ar")

    contact_method: Mapped[ContactMethod] = mapped_column(Enum(ContactMethod), default=ContactMethod.EMAIL)
    # Signup OTP was removed - accounts are active immediately, so this is
    # always True for new rows. Kept as a column because existing DBs have it.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    appointments = relationship(
        "Appointment", back_populates="patient", cascade="all, delete-orphan"
    )
