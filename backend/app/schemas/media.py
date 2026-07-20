from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.media import MediaKind
from app.models.section import SectionKind
from app.storage import ALLOWED_IMAGE_TYPES


# --- Upload (presign -> browser PUTs to R2 -> confirm) -----------------------

class PresignRequest(BaseModel):
    kind: MediaKind
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)
    filename: Optional[str] = Field(default=None, max_length=255)

    @field_validator("content_type")
    @classmethod
    def _known_image_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_IMAGE_TYPES:
            raise ValueError(
                "Unsupported content_type. Allowed: " + ", ".join(sorted(ALLOWED_IMAGE_TYPES))
            )
        return v


class PresignResponse(BaseModel):
    upload_url: str
    object_key: str
    public_url: str
    content_type: str
    expires_in: int
    # The browser MUST replay these on its PUT (signed into the URL).
    required_headers: dict[str, str]


class MediaConfirm(BaseModel):
    """Called after the browser PUT succeeds; persists the MediaAsset row."""

    object_key: str = Field(max_length=400)
    kind: MediaKind
    alt_ar: Optional[str] = Field(default=None, max_length=300)
    alt_tr: Optional[str] = Field(default=None, max_length=300)
    section_id: Optional[int] = None
    content_type: Optional[str] = Field(default=None, max_length=100)
    size_bytes: Optional[int] = Field(default=None, ge=0)


class MediaUpdate(BaseModel):
    alt_ar: Optional[str] = Field(default=None, max_length=300)
    alt_tr: Optional[str] = Field(default=None, max_length=300)
    sort_order: Optional[int] = None
    # Reassign the image to a section (or detach with null).
    section_id: Optional[int] = None


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    section_id: Optional[int] = None
    kind: MediaKind
    object_key: str
    url: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    alt_ar: Optional[str] = None
    alt_tr: Optional[str] = None
    sort_order: int
    created_at: datetime


# --- Homepage content sections ----------------------------------------------

class SectionCreate(BaseModel):
    kind: SectionKind = SectionKind.GALLERY
    title_ar: Optional[str] = Field(default=None, max_length=200)
    title_tr: Optional[str] = Field(default=None, max_length=200)
    body_ar: Optional[str] = Field(default=None, max_length=5000)
    body_tr: Optional[str] = Field(default=None, max_length=5000)
    sort_order: Optional[int] = None
    is_active: bool = True


class SectionUpdate(BaseModel):
    kind: Optional[SectionKind] = None
    title_ar: Optional[str] = Field(default=None, max_length=200)
    title_tr: Optional[str] = Field(default=None, max_length=200)
    body_ar: Optional[str] = Field(default=None, max_length=5000)
    body_tr: Optional[str] = Field(default=None, max_length=5000)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    kind: SectionKind
    title_ar: Optional[str] = None
    title_tr: Optional[str] = None
    body_ar: Optional[str] = None
    body_tr: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    images: List[MediaOut] = []


class SectionReorder(BaseModel):
    """Full ordered list of this clinic's section ids, top to bottom."""

    section_ids: List[int] = Field(min_length=1)


# --- Public (no-auth) homepage payload --------------------------------------

class PublicMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    alt_ar: Optional[str] = None
    alt_tr: Optional[str] = None


class PublicSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: SectionKind
    title_ar: Optional[str] = None
    title_tr: Optional[str] = None
    body_ar: Optional[str] = None
    body_tr: Optional[str] = None
    images: List[PublicMediaOut] = []
