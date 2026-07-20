"""add per-clinic theming (theme_preset + theme_overrides)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19

Session 3. Adds two columns to `clinics`:
  - theme_preset  : name of a developer-controlled preset (app/themes/*.json),
                    switchable only by the superadmin. Defaults to "default".
  - theme_overrides: JSON blob of the admin-editable layer (colors, logo,
                    display name + hero/contact/footer texts) merged on top of
                    the preset to produce the effective theme. Defaults to {}.

Both are NOT NULL with server defaults so existing rows populate cleanly. On an
existing prod DB (Neon) this only ALTERs `clinics` - no data touched. Fresh
SQLite dev DBs get these columns straight from create_all() and never run this.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clinics") as batch:
        batch.add_column(
            sa.Column("theme_preset", sa.String(length=50), nullable=False, server_default="default")
        )
        batch.add_column(
            sa.Column("theme_overrides", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("clinics") as batch:
        batch.drop_column("theme_overrides")
        batch.drop_column("theme_preset")
