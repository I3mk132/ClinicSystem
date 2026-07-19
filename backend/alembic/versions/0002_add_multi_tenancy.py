"""add multi-tenancy (clinics + clinic_id)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19

Session 2a. Adds the `clinics` tenant table, seeds a single "default" clinic,
and adds a nullable `clinic_id` FK to every tenant-owned table, backfilling all
existing rows to the default clinic. Columns stay NULLABLE here on purpose: the
write paths (routers) don't set clinic_id until Session 2b, which then flips
them to NOT NULL and adds per-tenant unique constraints.

On existing databases (Neon): `alembic stamp 0001` first (the pre-tenancy
tables already exist), then `alembic upgrade head` runs this migration.
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every tenant-owned table gets a clinic_id column.
TENANT_TABLES = [
    "users",
    "departments",
    "doctors",
    "doctor_availabilities",
    "doctor_time_off",
    "appointments",
    "verification_codes",
    "api_keys",
]


def upgrade() -> None:
    op.create_table(
        "clinics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("custom_domain", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinics_slug", "clinics", ["slug"], unique=True)
    op.create_index("ix_clinics_custom_domain", "clinics", ["custom_domain"], unique=True)

    # Seed a single default tenant to own all pre-existing rows.
    clinics = sa.table(
        "clinics",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(
        clinics,
        [{"slug": "default", "name": "Default Clinic", "is_active": True, "created_at": datetime.utcnow()}],
    )

    # Add the FK column to each tenant table (batch mode so SQLite can ALTER),
    # then backfill existing rows to the default clinic.
    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("clinic_id", sa.Integer(), nullable=True))
            batch.create_index(f"ix_{table}_clinic_id", ["clinic_id"])
            batch.create_foreign_key(f"fk_{table}_clinic_id", "clinics", ["clinic_id"], ["id"])
        op.execute(
            f"UPDATE {table} SET clinic_id = (SELECT id FROM clinics WHERE slug = 'default') "
            "WHERE clinic_id IS NULL"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_clinic_id", type_="foreignkey")
            batch.drop_index(f"ix_{table}_clinic_id")
            batch.drop_column("clinic_id")
    op.drop_index("ix_clinics_custom_domain", table_name="clinics")
    op.drop_index("ix_clinics_slug", table_name="clinics")
    op.drop_table("clinics")
