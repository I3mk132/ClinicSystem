"""add media library + homepage content sections

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-20

Session 4. Two NEW tenant-owned tables (both carry a NOT NULL clinic_id):

  - clinic_sections : configurable homepage content blocks (gallery / equipment
                      / team / custom), bilingual title + body, ordered by
                      sort_order, is_active gate for public visibility.
  - media_assets    : Cloudflare R2 image handles. object_key is unique and
                      ALWAYS clinic-prefixed (clinics/{clinic_id}/...). A
                      nullable section_id FK (ON DELETE SET NULL) attaches an
                      image to a homepage section; logo / doctor-photo assets
                      leave it NULL.

Pure additive create_table - no existing table is touched. Fresh SQLite dev DBs
get these straight from create_all() and never run this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SECTION_KIND = sa.Enum("GALLERY", "EQUIPMENT", "TEAM", "CUSTOM", name="sectionkind")
_MEDIA_KIND = sa.Enum("LOGO", "DOCTOR_PHOTO", "EQUIPMENT", "GALLERY", "SECTION_IMAGE", name="mediakind")


def upgrade() -> None:
    op.create_table(
        "clinic_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("kind", _SECTION_KIND, nullable=False),
        sa.Column("title_ar", sa.String(length=200), nullable=True),
        sa.Column("title_tr", sa.String(length=200), nullable=True),
        sa.Column("body_ar", sa.Text(), nullable=True),
        sa.Column("body_tr", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinic_sections_id", "clinic_sections", ["id"])
    op.create_index("ix_clinic_sections_clinic_id", "clinic_sections", ["clinic_id"])
    op.create_index("ix_clinic_sections_sort_order", "clinic_sections", ["sort_order"])

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("kind", _MEDIA_KIND, nullable=False),
        sa.Column("object_key", sa.String(length=400), nullable=False),
        sa.Column("url", sa.String(length=600), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("alt_ar", sa.String(length=300), nullable=True),
        sa.Column("alt_tr", sa.String(length=300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["clinic_sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_id", "media_assets", ["id"])
    op.create_index("ix_media_assets_clinic_id", "media_assets", ["clinic_id"])
    op.create_index("ix_media_assets_section_id", "media_assets", ["section_id"])
    op.create_index("ix_media_assets_object_key", "media_assets", ["object_key"], unique=True)


def downgrade() -> None:
    op.drop_table("media_assets")
    op.drop_table("clinic_sections")
    _MEDIA_KIND.drop(op.get_bind(), checkfirst=True)
    _SECTION_KIND.drop(op.get_bind(), checkfirst=True)
