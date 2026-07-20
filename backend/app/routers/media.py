"""
Media library + homepage content sections (Session 4).

Three concerns, one file:

  - admin_router  (/api/v1/admin/media, /api/v1/admin/sections): clinic-admin
    only, everything scoped to admin.clinic_id. Presign uploads, confirm/list/
    edit/delete media, and full CRUD + reorder of homepage sections.
  - public_router (/api/v1/public/sections): NO auth, tenant from the X-Clinic
    header - the homepage reads its active sections + images here.

Uploads never pass through this API: POST /admin/media/presign returns a
short-lived R2 PUT URL for a SERVER-GENERATED, clinic-prefixed object key; the
browser PUTs the bytes to R2, then POST /admin/media persists the MediaAsset
row. The clinic prefix on the key (clinics/{clinic_id}/...) is the tenant
isolation - a key from another clinic's prefix is rejected on confirm/delete.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import storage
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_clinic
from app.models.clinic import Clinic
from app.models.media import MediaAsset
from app.models.section import ClinicSection
from app.models.user import User
from app.schemas.media import (
    MediaConfirm,
    MediaOut,
    MediaUpdate,
    PresignRequest,
    PresignResponse,
    PublicSectionOut,
    SectionCreate,
    SectionOut,
    SectionReorder,
    SectionUpdate,
)

logger = logging.getLogger("app.media")

admin_router = APIRouter(prefix="/admin", tags=["Media & Homepage"])
public_router = APIRouter(prefix="/public", tags=["Media & Homepage"])


def _require_storage() -> None:
    if not storage.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media storage (R2) is not configured on this server",
        )


def _owned_section(db: Session, section_id: int, clinic_id: int) -> ClinicSection:
    section = (
        db.query(ClinicSection)
        .filter(ClinicSection.id == section_id, ClinicSection.clinic_id == clinic_id)
        .first()
    )
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


# ===========================================================================
# Media upload + library (admin)
# ===========================================================================

@admin_router.post("/media/presign", response_model=PresignResponse)
def presign_upload(
    payload: PresignRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _require_storage()
    if payload.size_bytes > settings.MEDIA_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MEDIA_MAX_BYTES} byte limit",
        )
    # Key is generated server-side and clinic-prefixed - the client never
    # supplies it, so it can only ever upload into its own clinic's prefix.
    object_key = storage.build_object_key(admin.clinic_id, payload.content_type)
    upload_url = storage.presign_put(object_key, payload.content_type)
    return PresignResponse(
        upload_url=upload_url,
        object_key=object_key,
        public_url=storage.public_url(object_key),
        content_type=payload.content_type,
        expires_in=settings.MEDIA_PRESIGN_EXPIRE_SECONDS,
        required_headers={"Content-Type": payload.content_type},
    )


@admin_router.post("/media", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
def confirm_media(
    payload: MediaConfirm,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _require_storage()
    # Reject a key that isn't under THIS clinic's prefix - the only way a key is
    # valid is if we presigned it for this clinic moments ago.
    if not storage.belongs_to_clinic(payload.object_key, admin.clinic_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Object key is not in this clinic's namespace")

    existing = db.query(MediaAsset).filter(MediaAsset.object_key == payload.object_key).first()
    if existing:
        # Idempotent re-confirm (client retry) - don't create a duplicate row.
        if existing.clinic_id != admin.clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Object key already registered to another clinic")
        return existing

    section_id = None
    if payload.section_id is not None:
        _owned_section(db, payload.section_id, admin.clinic_id)  # validate ownership
        section_id = payload.section_id

    asset = MediaAsset(
        clinic_id=admin.clinic_id,
        section_id=section_id,
        kind=payload.kind,
        object_key=payload.object_key,
        url=storage.public_url(payload.object_key),
        content_type=payload.content_type or storage.guess_content_type_from_key(payload.object_key),
        size_bytes=payload.size_bytes,
        alt_ar=payload.alt_ar,
        alt_tr=payload.alt_tr,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@admin_router.get("/media", response_model=List[MediaOut])
def list_media(
    kind: Optional[str] = None,
    section_id: Optional[int] = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(MediaAsset).filter(MediaAsset.clinic_id == admin.clinic_id)
    if kind is not None:
        query = query.filter(MediaAsset.kind == kind)
    if section_id is not None:
        query = query.filter(MediaAsset.section_id == section_id)
    return query.order_by(MediaAsset.sort_order, MediaAsset.created_at.desc()).all()


@admin_router.patch("/media/{media_id}", response_model=MediaOut)
def update_media(
    media_id: int,
    payload: MediaUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    asset = (
        db.query(MediaAsset)
        .filter(MediaAsset.id == media_id, MediaAsset.clinic_id == admin.clinic_id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    updates = payload.model_dump(exclude_unset=True)
    if "section_id" in updates and updates["section_id"] is not None:
        _owned_section(db, updates["section_id"], admin.clinic_id)  # can't attach to another clinic's section
    for field, value in updates.items():
        setattr(asset, field, value)
    db.commit()
    db.refresh(asset)
    return asset


@admin_router.delete("/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    media_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    asset = (
        db.query(MediaAsset)
        .filter(MediaAsset.id == media_id, MediaAsset.clinic_id == admin.clinic_id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    # Best-effort R2 delete: a failure there must not strand the DB row (the
    # object can be swept later); the row is the source of truth for the UI.
    if storage.is_enabled():
        try:
            storage.delete_object(asset.object_key)
        except Exception:  # noqa: BLE001 - R2 outage/permission shouldn't block DB cleanup
            logger.warning("R2 delete failed for %s; removing DB row anyway", asset.object_key)
    db.delete(asset)
    db.commit()


# ===========================================================================
# Homepage content sections (admin CRUD + reorder)
# ===========================================================================

def _next_sort_order(db: Session, clinic_id: int) -> int:
    last = (
        db.query(ClinicSection)
        .filter(ClinicSection.clinic_id == clinic_id)
        .order_by(ClinicSection.sort_order.desc())
        .first()
    )
    return (last.sort_order + 1) if last else 0


@admin_router.get("/sections", response_model=List[SectionOut])
def list_sections(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return (
        db.query(ClinicSection)
        .options(joinedload(ClinicSection.images))
        .filter(ClinicSection.clinic_id == admin.clinic_id)
        .order_by(ClinicSection.sort_order, ClinicSection.id)
        .all()
    )


@admin_router.post("/sections", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
def create_section(
    payload: SectionCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    if data.get("sort_order") is None:
        data["sort_order"] = _next_sort_order(db, admin.clinic_id)
    section = ClinicSection(clinic_id=admin.clinic_id, **data)
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@admin_router.patch("/sections/{section_id}", response_model=SectionOut)
def update_section(
    section_id: int,
    payload: SectionUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    section = _owned_section(db, section_id, admin.clinic_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(section, field, value)
    db.commit()
    db.refresh(section)
    return section


@admin_router.post("/sections/reorder", response_model=List[SectionOut])
def reorder_sections(
    payload: SectionReorder,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    sections = (
        db.query(ClinicSection)
        .filter(ClinicSection.clinic_id == admin.clinic_id)
        .all()
    )
    by_id = {s.id: s for s in sections}
    # Every id must belong to this clinic; ignore stragglers not listed.
    for pos, sid in enumerate(payload.section_ids):
        if sid not in by_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Section {sid} not found")
        by_id[sid].sort_order = pos
    db.commit()
    return (
        db.query(ClinicSection)
        .options(joinedload(ClinicSection.images))
        .filter(ClinicSection.clinic_id == admin.clinic_id)
        .order_by(ClinicSection.sort_order, ClinicSection.id)
        .all()
    )


@admin_router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(
    section_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    section = _owned_section(db, section_id, admin.clinic_id)
    # Detach (don't delete) the images so the underlying R2 objects survive and
    # can be re-used or cleaned up from the media library.
    for img in list(section.images):
        img.section_id = None
    db.delete(section)
    db.commit()


# ===========================================================================
# Public homepage sections (no auth, X-Clinic tenant)
# ===========================================================================

@public_router.get("/sections", response_model=List[PublicSectionOut])
def public_sections(clinic: Clinic = Depends(get_current_clinic), db: Session = Depends(get_db)):
    return (
        db.query(ClinicSection)
        .options(joinedload(ClinicSection.images))
        .filter(ClinicSection.clinic_id == clinic.id, ClinicSection.is_active.is_(True))
        .order_by(ClinicSection.sort_order, ClinicSection.id)
        .all()
    )
