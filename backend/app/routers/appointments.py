from datetime import date as date_type
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_user
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentStatusUpdate
from app.services import find_matching_slot

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def _load(query):
    return query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor).joinedload(Doctor.department),
        joinedload(Appointment.department),
    )


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A logged-in patient books an appointment. This is the core booking action."""
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id, Doctor.is_active.is_(True)).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if doctor.department_id != payload.department_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor does not belong to this department")
    if payload.appointment_date < date_type.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book a date in the past")

    slot = find_matching_slot(db, payload.doctor_id, payload.appointment_date, payload.start_time)
    if slot is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This time is outside the doctor's working hours")
    if not slot.is_available:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This time slot is no longer available")

    appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=payload.doctor_id,
        department_id=payload.department_id,
        appointment_date=payload.appointment_date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        notes=payload.notes,
        status=AppointmentStatus.CONFIRMED,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return _load(db.query(Appointment)).filter(Appointment.id == appointment.id).first()


@router.get("/me", response_model=List[AppointmentOut])
def my_appointments(
    upcoming_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = _load(db.query(Appointment)).filter(Appointment.patient_id == current_user.id)
    if upcoming_only:
        query = query.filter(Appointment.appointment_date >= date_type.today())
    return query.order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc()).all()


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_my_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if appointment.patient_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot cancel this appointment")
    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is already cancelled")

    appointment.status = AppointmentStatus.CANCELLED
    db.commit()
    return _load(db.query(Appointment)).filter(Appointment.id == appointment.id).first()


# ---------------------------------------------------------------------------
# Admin: full visibility & management of every booking
# ---------------------------------------------------------------------------
@router.get("", response_model=List[AppointmentOut], dependencies=[Depends(get_current_admin)])
def list_all_appointments(
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status_filter: Optional[AppointmentStatus] = Query(default=None, alias="status"),
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    db: Session = Depends(get_db),
):
    query = _load(db.query(Appointment))
    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if department_id is not None:
        query = query.filter(Appointment.department_id == department_id)
    if status_filter is not None:
        query = query.filter(Appointment.status == status_filter)
    if date_from is not None:
        query = query.filter(Appointment.appointment_date >= date_from)
    if date_to is not None:
        query = query.filter(Appointment.appointment_date <= date_to)
    return query.order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc()).all()


@router.patch("/{appointment_id}/status", response_model=AppointmentOut,
              dependencies=[Depends(get_current_admin)])
def update_appointment_status(appointment_id: int, payload: AppointmentStatusUpdate, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    appointment.status = payload.status
    db.commit()
    return _load(db.query(Appointment)).filter(Appointment.id == appointment.id).first()
