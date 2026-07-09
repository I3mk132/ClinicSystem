from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus


class PublicAppointmentCreate(BaseModel):
    """
    Booking payload for server-to-server / bot integrations.
    No login is required - the caller (e.g. a WhatsApp/Telegram bot) already
    knows the patient's name and phone number from the chat platform itself.
    If no account exists for that phone number yet, one is created
    automatically (see routers/public.py).
    """

    doctor_id: int
    department_id: int
    appointment_date: date
    start_time: time
    patient_full_name: str = Field(min_length=2, max_length=150)
    patient_phone: str = Field(min_length=5, max_length=30)
    notes: Optional[str] = Field(default=None, max_length=500)


class PublicDoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    title_ar: Optional[str] = None
    title_tr: Optional[str] = None
    photo_url: Optional[str] = None
    department_id: int


class PublicDepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name_ar: str
    name_tr: str
    icon: str


class PublicAppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: AppointmentStatus
    notes: Optional[str] = None
    created_at: datetime

    doctor: PublicDoctorOut
    department: PublicDepartmentOut
    patient_full_name: str
    patient_phone: Optional[str] = None
