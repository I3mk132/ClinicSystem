from datetime import date as date_type
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_clinic
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.schedule import DoctorAvailability, DoctorTimeOff
from app.models.user import User
from app.schemas.schedule import (
    AvailabilityCreate,
    AvailabilityOut,
    AvailabilityUpdate,
    AvailableSlot,
    TimeOffCreate,
    TimeOffOut,
)
from app.services import get_slots_for_doctor_on_date

router = APIRouter(tags=["Schedules"])


def _clinic_doctor(db: Session, doctor_id: int, clinic_id: int) -> Doctor:
    """Fetch a doctor that belongs to the given clinic, or 404. Prevents a caller
    from reading/writing schedule data for another clinic's doctor by id."""
    doctor = (
        db.query(Doctor)
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic_id)
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return doctor


# ---------------------------------------------------------------------------
# Public: available slots for booking (the heart of the booking portal)
# ---------------------------------------------------------------------------
@router.get("/doctors/{doctor_id}/available-slots", response_model=List[AvailableSlot])
def available_slots(
    doctor_id: int,
    target_date: date_type = Query(..., alias="date"),
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    _clinic_doctor(db, doctor_id, clinic.id)  # 404 if the doctor isn't in this clinic
    if target_date < date_type.today():
        return []

    # Safe cross-tenant-wise: every availability/time-off/appointment the service
    # reads is keyed to this doctor_id, which we just proved belongs to `clinic`.
    slots = get_slots_for_doctor_on_date(db, doctor_id, target_date)
    return [AvailableSlot(start_time=s.start_time, end_time=s.end_time, is_available=s.is_available) for s in slots]


# ---------------------------------------------------------------------------
# Admin: weekly availability templates
# ---------------------------------------------------------------------------
@router.get("/availabilities", response_model=List[AvailabilityOut])
def list_availabilities(
    doctor_id: int | None = None,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    """Public read (so the frontend can show 'works on: Sun, Tue, Thu' badges)."""
    query = db.query(DoctorAvailability).filter(DoctorAvailability.clinic_id == clinic.id)
    if doctor_id is not None:
        query = query.filter(DoctorAvailability.doctor_id == doctor_id)
    return query.order_by(DoctorAvailability.weekday, DoctorAvailability.start_time).all()


@router.post("/availabilities", response_model=AvailabilityOut, status_code=status.HTTP_201_CREATED)
def create_availability(
    payload: AvailabilityCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_time must be before end_time")
    _clinic_doctor(db, payload.doctor_id, admin.clinic_id)

    availability = DoctorAvailability(clinic_id=admin.clinic_id, **payload.model_dump())
    db.add(availability)
    db.commit()
    db.refresh(availability)
    return availability


@router.patch("/availabilities/{availability_id}", response_model=AvailabilityOut)
def update_availability(
    availability_id: int,
    payload: AvailabilityUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    availability = (
        db.query(DoctorAvailability)
        .filter(DoctorAvailability.id == availability_id, DoctorAvailability.clinic_id == admin.clinic_id)
        .first()
    )
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability rule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(availability, field, value)
    db.commit()
    db.refresh(availability)
    return availability


@router.delete("/availabilities/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_availability(
    availability_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    availability = (
        db.query(DoctorAvailability)
        .filter(DoctorAvailability.id == availability_id, DoctorAvailability.clinic_id == admin.clinic_id)
        .first()
    )
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability rule not found")
    db.delete(availability)
    db.commit()


# ---------------------------------------------------------------------------
# Admin: time off / holidays
# ---------------------------------------------------------------------------
@router.get("/time-off", response_model=List[TimeOffOut])
def list_time_off(
    doctor_id: int | None = None,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    query = db.query(DoctorTimeOff).filter(DoctorTimeOff.clinic_id == clinic.id)
    if doctor_id is not None:
        query = query.filter(DoctorTimeOff.doctor_id == doctor_id)
    return query.order_by(DoctorTimeOff.date).all()


@router.post("/time-off", response_model=TimeOffOut, status_code=status.HTTP_201_CREATED)
def create_time_off(
    payload: TimeOffCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _clinic_doctor(db, payload.doctor_id, admin.clinic_id)
    time_off = DoctorTimeOff(clinic_id=admin.clinic_id, **payload.model_dump())
    db.add(time_off)
    db.commit()
    db.refresh(time_off)
    return time_off


@router.delete("/time-off/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_off(
    time_off_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    time_off = (
        db.query(DoctorTimeOff)
        .filter(DoctorTimeOff.id == time_off_id, DoctorTimeOff.clinic_id == admin.clinic_id)
        .first()
    )
    if not time_off:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time-off entry not found")
    db.delete(time_off)
    db.commit()
