from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_clinic
from app.models.clinic import Clinic
from app.models.department import Department
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentOut, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=List[DepartmentOut])
def list_departments(
    include_inactive: bool = False,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    """Public: list departments for the booking portal (scoped to the X-Clinic tenant)."""
    query = db.query(Department).filter(Department.clinic_id == clinic.id)
    if not include_inactive:
        query = query.filter(Department.is_active.is_(True))
    return query.order_by(Department.id).all()


@router.get("/{department_id}", response_model=DepartmentOut)
def get_department(
    department_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.clinic_id == clinic.id)
        .first()
    )
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    department = Department(clinic_id=admin.clinic_id, **payload.model_dump())
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.patch("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.clinic_id == admin.clinic_id)
        .first()
    )
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(department, field, value)
    db.commit()
    db.refresh(department)
    return department


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.clinic_id == admin.clinic_id)
        .first()
    )
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    if department.doctors:
        # Doctors (and their appointments) reference this row - deleting it would
        # orphan them (SQLite) or blow up on the FK (PostgreSQL/MySQL).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department still has doctors - move or delete them first, or mark the department inactive",
        )
    db.delete(department)
    db.commit()
