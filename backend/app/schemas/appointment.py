from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus
from app.schemas.department import DepartmentOut
from app.schemas.doctor import DoctorOut
from app.schemas.user import UserOut


class AppointmentCreate(BaseModel):
    doctor_id: int
    department_id: int
    appointment_date: date
    start_time: time
    notes: Optional[str] = Field(default=None, max_length=500)


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: AppointmentStatus
    notes: Optional[str] = None
    created_at: datetime

    patient: UserOut
    doctor: DoctorOut
    department: DepartmentOut
