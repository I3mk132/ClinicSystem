from datetime import date as date_type
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.doctor import Doctor
from app.models.schedule import DoctorAvailability, DoctorTimeOff
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


# ---------------------------------------------------------------------------
# Public: available slots for booking (the heart of the booking portal)
# ---------------------------------------------------------------------------
@router.get("/doctors/{doctor_id}/available-slots", response_model=List[AvailableSlot])
def available_slots(
    doctor_id: int,
    target_date: date_type = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if target_date < date_type.today():
        return []

    slots = get_slots_for_doctor_on_date(db, doctor_id, target_date)
    return [AvailableSlot(start_time=s.start_time, end_time=s.end_time, is_available=s.is_available) for s in slots]


# ---------------------------------------------------------------------------
# Admin: weekly availability templates
# ---------------------------------------------------------------------------
@router.get("/availabilities", response_model=List[AvailabilityOut])
def list_availabilities(doctor_id: int | None = None, db: Session = Depends(get_db)):
    """Public read (so the frontend can show 'works on: Sun, Tue, Thu' badges)."""
    query = db.query(DoctorAvailability)
    if doctor_id is not None:
        query = query.filter(DoctorAvailability.doctor_id == doctor_id)
    return query.order_by(DoctorAvailability.weekday, DoctorAvailability.start_time).all()


@router.post("/availabilities", response_model=AvailabilityOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(get_current_admin)])
def create_availability(payload: AvailabilityCreate, db: Session = Depends(get_db)):
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_time must be before end_time")
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    availability = DoctorAvailability(**payload.model_dump())
    db.add(availability)
    db.commit()
    db.refresh(availability)
    return availability


@router.patch("/availabilities/{availability_id}", response_model=AvailabilityOut,
              dependencies=[Depends(get_current_admin)])
def update_availability(availability_id: int, payload: AvailabilityUpdate, db: Session = Depends(get_db)):
    availability = db.query(DoctorAvailability).filter(DoctorAvailability.id == availability_id).first()
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability rule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(availability, field, value)
    db.commit()
    db.refresh(availability)
    return availability


@router.delete("/availabilities/{availability_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(get_current_admin)])
def delete_availability(availability_id: int, db: Session = Depends(get_db)):
    availability = db.query(DoctorAvailability).filter(DoctorAvailability.id == availability_id).first()
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability rule not found")
    db.delete(availability)
    db.commit()


# ---------------------------------------------------------------------------
# Admin: time off / holidays
# ---------------------------------------------------------------------------
@router.get("/time-off", response_model=List[TimeOffOut])
def list_time_off(doctor_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(DoctorTimeOff)
    if doctor_id is not None:
        query = query.filter(DoctorTimeOff.doctor_id == doctor_id)
    return query.order_by(DoctorTimeOff.date).all()


@router.post("/time-off", response_model=TimeOffOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(get_current_admin)])
def create_time_off(payload: TimeOffCreate, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    time_off = DoctorTimeOff(**payload.model_dump())
    db.add(time_off)
    db.commit()
    db.refresh(time_off)
    return time_off


@router.delete("/time-off/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(get_current_admin)])
def delete_time_off(time_off_id: int, db: Session = Depends(get_db)):
    time_off = db.query(DoctorTimeOff).filter(DoctorTimeOff.id == time_off_id).first()
    if not time_off:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time-off entry not found")
    db.delete(time_off)
    db.commit()
