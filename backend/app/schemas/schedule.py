from datetime import date, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AvailabilityBase(BaseModel):
    doctor_id: int
    weekday: int = Field(ge=0, le=6, description="0=Monday ... 6=Sunday")
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(default=30, ge=5, le=240)
    is_active: bool = True


class AvailabilityCreate(AvailabilityBase):
    pass


class AvailabilityUpdate(BaseModel):
    weekday: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slot_duration_minutes: Optional[int] = Field(default=None, ge=5, le=240)
    is_active: Optional[bool] = None


class AvailabilityOut(AvailabilityBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TimeOffBase(BaseModel):
    doctor_id: int
    date: date
    reason: Optional[str] = None


class TimeOffCreate(TimeOffBase):
    pass


class TimeOffOut(TimeOffBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AvailableSlot(BaseModel):
    """A single bookable time slot returned to the frontend for a doctor + date."""

    start_time: time
    end_time: time
    is_available: bool
