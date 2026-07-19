from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Doctor(Base):
    """
    A doctor profile. Kept separate from `User` on purpose: a doctor does not
    necessarily need a login account for this MVP (the admin manages their
    schedule), which keeps the auth system simple while still allowing a
    doctor login role to be added later without a schema rewrite.
    """

    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(150), nullable=True)  # e.g. "استشاري جراحة"
    title_tr: Mapped[str] = mapped_column(String(150), nullable=True)  # e.g. "Genel Cerrahi Uzmanı"
    bio_ar: Mapped[str] = mapped_column(Text, nullable=True)
    bio_tr: Mapped[str] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str] = mapped_column(String(300), nullable=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department = relationship("Department", back_populates="doctors")
    availabilities = relationship(
        "DoctorAvailability", back_populates="doctor", cascade="all, delete-orphan"
    )
    time_off = relationship(
        "DoctorTimeOff", back_populates="doctor", cascade="all, delete-orphan"
    )
    appointments = relationship("Appointment", back_populates="doctor")
