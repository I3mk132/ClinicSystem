import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SectionKind(str, enum.Enum):
    """The layout/intent of a homepage content block."""

    GALLERY = "gallery"       # a photo grid
    EQUIPMENT = "equipment"   # photos of clinic equipment/facilities
    TEAM = "team"             # staff/team photos
    CUSTOM = "custom"         # free title + body (+ optional images)


class ClinicSection(Base):
    """
    A configurable homepage content block for a clinic (Session 4). Ordered by
    `sort_order`; only `is_active` sections are served publicly. Bilingual title
    and body (Arabic + Turkish). Its attached images are `MediaAsset` rows whose
    `section_id` points back here.

    Tenant-owned: `clinic_id` is NOT NULL and every query filters by it.
    """

    __tablename__ = "clinic_sections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    kind: Mapped[SectionKind] = mapped_column(Enum(SectionKind), nullable=False, default=SectionKind.GALLERY)
    title_ar: Mapped[str] = mapped_column(String(200), nullable=True)
    title_tr: Mapped[str] = mapped_column(String(200), nullable=True)
    body_ar: Mapped[str] = mapped_column(Text, nullable=True)
    body_tr: Mapped[str] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    images = relationship(
        "MediaAsset",
        back_populates="section",
        order_by="MediaAsset.sort_order",
        # Detach images (set section_id NULL) rather than delete them when a
        # section is removed - the underlying R2 object may still be wanted.
        passive_deletes=True,
    )
