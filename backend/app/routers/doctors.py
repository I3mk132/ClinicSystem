from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_clinic
from app.models.clinic import Clinic
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.doctor import DoctorCreate, DoctorOut, DoctorUpdate

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=List[DoctorOut])
def list_doctors(
    department_id: Optional[int] = None,
    include_inactive: bool = False,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    """Public: list doctors, optionally filtered by department, for the booking portal."""
    query = (
        db.query(Doctor)
        .options(joinedload(Doctor.department))
        .filter(Doctor.clinic_id == clinic.id)
    )
    if department_id is not None:
        query = query.filter(Doctor.department_id == department_id)
    if not include_inactive:
        query = query.filter(Doctor.is_active.is_(True))
    return query.order_by(Doctor.full_name).all()


@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(
    doctor_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.department))
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic.id)
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return doctor


@router.post("", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
def create_doctor(
    payload: DoctorCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # The doctor's department must belong to the same clinic.
    department = (
        db.query(Department)
        .filter(Department.id == payload.department_id, Department.clinic_id == admin.clinic_id)
        .first()
    )
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    doctor = Doctor(clinic_id=admin.clinic_id, **payload.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.patch("/{doctor_id}", response_model=DoctorOut)
def update_doctor(
    doctor_id: int,
    payload: DoctorUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    doctor = (
        db.query(Doctor)
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == admin.clinic_id)
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    updates = payload.model_dump(exclude_unset=True)
    # A department reassignment must stay within the same clinic.
    if updates.get("department_id") is not None:
        dept = (
            db.query(Department)
            .filter(Department.id == updates["department_id"], Department.clinic_id == admin.clinic_id)
            .first()
        )
        if not dept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    for field, value in updates.items():
        setattr(doctor, field, value)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor(
    doctor_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    doctor = (
        db.query(Doctor)
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == admin.clinic_id)
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if doctor.appointments:
        # Appointments keep a FK to the doctor (patients' booking history).
        # Deleting would orphan/violate - deactivate instead to hide the doctor.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor has appointments - mark them inactive instead of deleting",
        )
    db.delete(doctor)
    db.commit()
