from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DoctorAvailability(Base):
    """
    A recurring weekly working-hours template for a doctor.
    Example: Dr. X works Sundays 09:00-13:00 with 20-minute slots.
    Actual bookable slots for a given date are generated on the fly from
    this template (see services in routers/schedules.py), so changing a
    doctor's hours automatically applies to all future dates.
    """

    __tablename__ = "doctor_availabilities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Tenant owner (denormalized from doctor for direct filtering).
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time: Mapped[Time] = mapped_column(Time, nullable=False)
    end_time: Mapped[Time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="availabilities")


class DoctorTimeOff(Base):
    """A specific date (holiday, leave, fully booked externally...) where the doctor is unavailable."""

    __tablename__ = "doctor_time_off"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Tenant owner (denormalized from doctor for direct filtering).
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=True)

    doctor = relationship("Doctor", back_populates="time_off")
