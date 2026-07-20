import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MediaKind(str, enum.Enum):
    """What an uploaded image is used for. Drives where it can be attached."""

    LOGO = "logo"
    DOCTOR_PHOTO = "doctor_photo"
    EQUIPMENT = "equipment"
    GALLERY = "gallery"
    SECTION_IMAGE = "section_image"


class MediaAsset(Base):
    """
    An image stored in Cloudflare R2 (Session 4). The bytes live in R2; this row
    is the tenant-scoped metadata/handle for them.

    `object_key` is ALWAYS prefixed with the owning clinic id
    (`clinics/{clinic_id}/{uuid}.ext`) - that prefix is what isolates one
    clinic's media from another's in the single shared bucket. The backend
    generates the key server-side on presign; the browser never chooses it.

    `section_id` is nullable: gallery/equipment/section images belong to a
    homepage `ClinicSection`; a logo or a doctor photo has `section_id=NULL`
    (it is referenced by URL from the theme overrides / doctor row instead).
    """

    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("clinic_sections.id", ondelete="SET NULL"), index=True, nullable=True
    )
    kind: Mapped[MediaKind] = mapped_column(Enum(MediaKind), nullable=False)
    # Globally unique because it is already clinic-prefixed; also what we delete
    # from R2 by. The public URL is R2_PUBLIC_BASE_URL + "/" + object_key.
    object_key: Mapped[str] = mapped_column(String(400), unique=True, index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(600), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    alt_ar: Mapped[str] = mapped_column(String(300), nullable=True)
    alt_tr: Mapped[str] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    section = relationship("ClinicSection", back_populates="images")
