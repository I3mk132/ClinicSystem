import enum
from datetime import date as date_, datetime, time as time_

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AppointmentStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Appointment(Base):
    """
    A booked slot: WHO (patient) booked WHAT (doctor/department) WHEN
    (date + start/end time) and its current status.
    A partial-unique constraint (doctor + date + start_time, only for
    non-cancelled bookings) is enforced at the service layer to keep this
    portable across SQLite/PostgreSQL/MySQL.
    """

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)

    appointment_date: Mapped[date_] = mapped_column(Date, nullable=False)
    start_time: Mapped[time_] = mapped_column(Time, nullable=False)
    end_time: Mapped[time_] = mapped_column(Time, nullable=False)

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), default=AppointmentStatus.CONFIRMED, nullable=False
    )
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patient = relationship("User", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    department = relationship("Department")
