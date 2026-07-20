"""
Per-clinic theming endpoints (Session 3).

Two routers, two audiences:

  - public_router: GET /api/v1/public/theme - NO auth, tenant resolved from the
    X-Clinic header (get_current_clinic). The frontend calls this on every page
    load to paint the clinic's colours/logo/texts. (It lives in its own router,
    not routers/public.py, because that one is guarded by an API key.)

  - admin_router: GET/PUT /api/v1/admin/theme - clinic-admin only, scoped to the
    admin's own clinic. Reads/writes the admin-editable overrides layer.

Switching a clinic's developer PRESET is a superadmin action and lives in
routers/superadmin.py, not here.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_clinic
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.clinic import AdminThemeOut, ThemeOverridesIn
from app.theme import effective_theme, preset_names

public_router = APIRouter(prefix="/public", tags=["Theme"])
admin_router = APIRouter(prefix="/admin", tags=["Theme"])


@public_router.get("/theme")
def get_public_theme(clinic: Clinic = Depends(get_current_clinic), db: Session = Depends(get_db)):
    """The merged effective theme for the X-Clinic tenant (no auth)."""
    return effective_theme(clinic)


def _admin_clinic(db: Session, admin: User) -> Clinic:
    clinic = db.query(Clinic).filter(Clinic.id == admin.clinic_id).first()
    if clinic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found")
    return clinic


@admin_router.get("/theme", response_model=AdminThemeOut)
def get_admin_theme(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    clinic = _admin_clinic(db, admin)
    return AdminThemeOut(
        preset=clinic.theme_preset,
        available_presets=preset_names(),
        overrides=clinic.theme_overrides or {},
        effective=effective_theme(clinic),
    )


@admin_router.put("/theme", response_model=AdminThemeOut)
def update_admin_theme(
    payload: ThemeOverridesIn,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Replace the clinic's admin overrides layer (preset is untouched)."""
    clinic = _admin_clinic(db, admin)
    # Store a sparse blob; reassign the whole dict so SQLAlchemy flags the JSON
    # column as dirty (plain JSON columns aren't mutation-tracked in place).
    clinic.theme_overrides = payload.model_dump(exclude_none=True)
    db.commit()
    db.refresh(clinic)
    return AdminThemeOut(
        preset=clinic.theme_preset,
        available_presets=preset_names(),
        overrides=clinic.theme_overrides or {},
        effective=effective_theme(clinic),
    )
