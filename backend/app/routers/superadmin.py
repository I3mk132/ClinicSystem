"""
Superadmin (developer) endpoints - manage the tenants themselves.

Guarded by get_current_superadmin (role SUPERADMIN, clinic_id NULL). These are
the ONLY endpoints that create/list/deactivate clinics or create a clinic's
first admin. Everything else in the API is scoped to a single clinic.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.dependencies import get_current_superadmin
from app.models.clinic import Clinic
from app.models.user import User, UserRole
from app.schemas.clinic import ClinicAdminCreate, ClinicCreate, ClinicOut, ClinicUpdate
from app.schemas.user import UserOut

router = APIRouter(
    prefix="/superadmin",
    tags=["Superadmin (Platform)"],
    dependencies=[Depends(get_current_superadmin)],
)


def _get_clinic(db: Session, clinic_id: int) -> Clinic:
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found")
    return clinic


@router.get("/clinics", response_model=List[ClinicOut])
def list_clinics(db: Session = Depends(get_db)):
    return db.query(Clinic).order_by(Clinic.id).all()


@router.post("/clinics", response_model=ClinicOut, status_code=status.HTTP_201_CREATED)
def create_clinic(payload: ClinicCreate, db: Session = Depends(get_db)):
    slug = payload.slug.strip().lower()
    if db.query(Clinic).filter(Clinic.slug == slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A clinic with this slug already exists")
    domain = payload.custom_domain.strip().lower() if payload.custom_domain else None
    if domain and db.query(Clinic).filter(Clinic.custom_domain == domain).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This custom domain is already in use")

    clinic = Clinic(slug=slug, name=payload.name, custom_domain=domain, is_active=True)
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.patch("/clinics/{clinic_id}", response_model=ClinicOut)
def update_clinic(clinic_id: int, payload: ClinicUpdate, db: Session = Depends(get_db)):
    clinic = _get_clinic(db, clinic_id)
    updates = payload.model_dump(exclude_unset=True)
    if "custom_domain" in updates and updates["custom_domain"]:
        domain = updates["custom_domain"].strip().lower()
        clash = (
            db.query(Clinic)
            .filter(Clinic.custom_domain == domain, Clinic.id != clinic_id)
            .first()
        )
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This custom domain is already in use")
        updates["custom_domain"] = domain
    for field, value in updates.items():
        setattr(clinic, field, value)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.post("/clinics/{clinic_id}/admins", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_clinic_admin(clinic_id: int, payload: ClinicAdminCreate, db: Session = Depends(get_db)):
    """Create a clinic-admin user for a clinic (its first login)."""
    clinic = _get_clinic(db, clinic_id)
    email = payload.email.lower()
    if db.query(User).filter(User.clinic_id == clinic.id, User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    admin = User(
        clinic_id=clinic.id,
        full_name=payload.full_name,
        email=email,
        preferred_language=payload.preferred_language,
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN,
        is_verified=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
