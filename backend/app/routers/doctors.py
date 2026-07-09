from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.doctor import Doctor
from app.schemas.doctor import DoctorCreate, DoctorOut, DoctorUpdate

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=List[DoctorOut])
def list_doctors(
    department_id: Optional[int] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """Public: list doctors, optionally filtered by department, for the booking portal."""
    query = db.query(Doctor).options(joinedload(Doctor.department))
    if department_id is not None:
        query = query.filter(Doctor.department_id == department_id)
    if not include_inactive:
        query = query.filter(Doctor.is_active.is_(True))
    return query.order_by(Doctor.full_name).all()


@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.department))
        .filter(Doctor.id == doctor_id)
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return doctor


@router.post("", response_model=DoctorOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(get_current_admin)])
def create_doctor(payload: DoctorCreate, db: Session = Depends(get_db)):
    doctor = Doctor(**payload.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.patch("/{doctor_id}", response_model=DoctorOut, dependencies=[Depends(get_current_admin)])
def update_doctor(doctor_id: int, payload: DoctorUpdate, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(get_current_admin)])
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    db.delete(doctor)
    db.commit()
