from datetime import date as date_type
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import hash_password
from app.dependencies import get_api_key, get_api_key_clinic
from app.models.appointment import Appointment, AppointmentStatus
from app.models.clinic import Clinic
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.user import ContactMethod, User, UserRole
from app.schemas.public import (
    PublicAppointmentCreate,
    PublicAppointmentOut,
    PublicDepartmentOut,
    PublicDoctorOut,
)
from app.schemas.schedule import AvailableSlot
from app.services import find_matching_slot, get_slots_for_doctor_on_date

# The tenant for these routes is ALWAYS the clinic that owns the API key
# (get_api_key_clinic), never a header - a key can't be pointed at another
# clinic's data. get_api_key stays as a router-level guard for defense in depth.
router = APIRouter(prefix="/public", tags=["Public API (Integrations)"], dependencies=[Depends(get_api_key)])


def _to_public_out(appt: Appointment) -> PublicAppointmentOut:
    return PublicAppointmentOut(
        id=appt.id,
        appointment_date=appt.appointment_date,
        start_time=appt.start_time,
        end_time=appt.end_time,
        status=appt.status,
        notes=appt.notes,
        created_at=appt.created_at,
        doctor=PublicDoctorOut.model_validate(appt.doctor),
        department=PublicDepartmentOut.model_validate(appt.department),
        patient_full_name=appt.patient.full_name,
        patient_phone=appt.patient.phone,
    )


# ---------------------------------------------------------------------------
# Read-only catalog - lets a bot show departments/doctors/available times
# ---------------------------------------------------------------------------
@router.get("/departments", response_model=List[PublicDepartmentOut])
def list_departments(clinic: Clinic = Depends(get_api_key_clinic), db: Session = Depends(get_db)):
    return (
        db.query(Department)
        .filter(Department.clinic_id == clinic.id, Department.is_active.is_(True))
        .order_by(Department.id)
        .all()
    )


@router.get("/doctors", response_model=List[PublicDoctorOut])
def list_doctors(
    department_id: Optional[int] = None,
    clinic: Clinic = Depends(get_api_key_clinic),
    db: Session = Depends(get_db),
):
    query = db.query(Doctor).filter(Doctor.clinic_id == clinic.id, Doctor.is_active.is_(True))
    if department_id is not None:
        query = query.filter(Doctor.department_id == department_id)
    return query.order_by(Doctor.full_name).all()


@router.get("/doctors/{doctor_id}/available-slots", response_model=List[AvailableSlot])
def available_slots(
    doctor_id: int,
    target_date: date_type = Query(..., alias="date"),
    clinic: Clinic = Depends(get_api_key_clinic),
    db: Session = Depends(get_db),
):
    doctor = (
        db.query(Doctor)
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic.id)
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if target_date < date_type.today():
        return []
    slots = get_slots_for_doctor_on_date(db, doctor_id, target_date)
    return [AvailableSlot(start_time=s.start_time, end_time=s.end_time, is_available=s.is_available) for s in slots]


# ---------------------------------------------------------------------------
# Booking - phone-number based, no login/password needed (bot already knows
# who it's talking to from the chat platform)
# ---------------------------------------------------------------------------
@router.post("/appointments", response_model=PublicAppointmentOut, status_code=status.HTTP_201_CREATED)
def create_public_appointment(
    payload: PublicAppointmentCreate,
    clinic: Clinic = Depends(get_api_key_clinic),
    db: Session = Depends(get_db),
):
    # Row lock -> no double booking under concurrency (see routers/appointments.py).
    doctor = (
        db.query(Doctor)
        .filter(Doctor.id == payload.doctor_id, Doctor.clinic_id == clinic.id, Doctor.is_active.is_(True))
        .with_for_update()
        .first()
    )
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

    # Find-or-create a lightweight patient record keyed by phone number WITHIN
    # this clinic (the same phone can be a patient of two different clinics).
    # These bot-created accounts have no email/password login by default;
    # the person can add those later from their profile if they also want
    # to use the web portal, or reset their password via /auth/password/forgot
    # using their phone number as the identifier.
    patient = (
        db.query(User)
        .filter(User.clinic_id == clinic.id, User.phone == payload.patient_phone)
        .first()
    )
    if not patient:
        patient = User(
            clinic_id=clinic.id,
            full_name=payload.patient_full_name,
            phone=payload.patient_phone,
            contact_method=ContactMethod.PHONE,
            hashed_password=hash_password(hash_password(payload.patient_phone)[:32]),  # unusable random-ish password
            role=UserRole.PATIENT,
            is_verified=True,  # trusted: the bot/integration already identified this person
        )
        db.add(patient)
        # flush (not commit) so the patient gets an id while keeping the doctor
        # row lock held until the appointment below is committed atomically.
        db.flush()

    appointment = Appointment(
        clinic_id=clinic.id,
        patient_id=patient.id,
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

    loaded = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor), joinedload(Appointment.department))
        .filter(Appointment.id == appointment.id)
        .first()
    )
    return _to_public_out(loaded)


@router.get("/appointments", response_model=List[PublicAppointmentOut])
def list_appointments_by_phone(
    phone: str = Query(..., min_length=5),
    clinic: Clinic = Depends(get_api_key_clinic),
    db: Session = Depends(get_db),
):
    patient = (
        db.query(User)
        .filter(User.clinic_id == clinic.id, User.phone == phone)
        .first()
    )
    if not patient:
        return []
    appointments = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor), joinedload(Appointment.department))
        .filter(Appointment.clinic_id == clinic.id, Appointment.patient_id == patient.id)
        .order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc())
        .all()
    )
    return [_to_public_out(a) for a in appointments]


@router.post("/appointments/{appointment_id}/cancel", response_model=PublicAppointmentOut)
def cancel_public_appointment(
    appointment_id: int,
    phone: str = Query(..., min_length=5),
    clinic: Clinic = Depends(get_api_key_clinic),
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor), joinedload(Appointment.department))
        .filter(Appointment.id == appointment_id, Appointment.clinic_id == clinic.id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if appointment.patient.phone != phone:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This appointment does not belong to this phone number")
    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is already cancelled")

    appointment.status = AppointmentStatus.CANCELLED
    db.commit()
    db.refresh(appointment)
    return _to_public_out(appointment)
