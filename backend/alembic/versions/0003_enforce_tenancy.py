"""enforce tenancy: clinic_id NOT NULL + per-tenant uniqueness

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19

Session 2b. After 0002 backfilled every existing row to the default clinic, this
migration:
  - makes clinic_id NOT NULL on all tenant tables EXCEPT users (a SUPERADMIN row
    has clinic_id NULL);
  - replaces the global unique index on users.email / users.phone with a
    per-clinic composite unique constraint;
  - adds per-clinic unique constraints on department names.

Fresh dev SQLite never runs this (create_all already builds the final schema);
it's for upgrading an existing DB (e.g. Neon). If the existing data has, within
one clinic, duplicate emails/phones or duplicate department names, the unique
constraints below will fail - dedupe first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# clinic_id -> NOT NULL everywhere except users (superadmin keeps it NULL).
NOT_NULL_TABLES = [
    "departments",
    "doctors",
    "doctor_availabilities",
    "doctor_time_off",
    "appointments",
    "verification_codes",
    "api_keys",
]


def upgrade() -> None:
    for table in NOT_NULL_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("clinic_id", existing_type=sa.Integer(), nullable=False)

    # users: global unique(email/phone) -> per-clinic composite unique.
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email")
        batch.drop_index("ix_users_phone")
        batch.create_index("ix_users_email", ["email"], unique=False)
        batch.create_index("ix_users_phone", ["phone"], unique=False)
        batch.create_unique_constraint("uq_users_clinic_email", ["clinic_id", "email"])
        batch.create_unique_constraint("uq_users_clinic_phone", ["clinic_id", "phone"])

    # departments: name unique per clinic.
    with op.batch_alter_table("departments") as batch:
        batch.create_unique_constraint("uq_departments_clinic_name_ar", ["clinic_id", "name_ar"])
        batch.create_unique_constraint("uq_departments_clinic_name_tr", ["clinic_id", "name_tr"])


def downgrade() -> None:
    with op.batch_alter_table("departments") as batch:
        batch.drop_constraint("uq_departments_clinic_name_tr", type_="unique")
        batch.drop_constraint("uq_departments_clinic_name_ar", type_="unique")

    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_clinic_phone", type_="unique")
        batch.drop_constraint("uq_users_clinic_email", type_="unique")
        batch.drop_index("ix_users_phone")
        batch.drop_index("ix_users_email")
        batch.create_index("ix_users_phone", ["phone"], unique=True)
        batch.create_index("ix_users_email", ["email"], unique=True)

    for table in NOT_NULL_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("clinic_id", existing_type=sa.Integer(), nullable=True)
