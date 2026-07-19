from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Clinic(Base):
    """
    A tenant. The system is multi-tenant SaaS using shared-schema row-level
    tenancy: one API deployment + one database serve many clinics, and every
    tenant-owned row carries a `clinic_id` (see the models that add it).

    A clinic is resolved per request either from the `X-Clinic` header (its
    `slug`, sent by the frontend) or by matching the request host against
    `custom_domain` - see `app/dependencies.py:get_current_clinic`.

    NOTE (Session 2 split): 2a lays the foundation (this model, nullable
    clinic_id columns, Alembic, resolution deps, tenant-scoped seed). 2b wires
    `clinic_id` into every router/query, flips the columns to NOT NULL with
    per-tenant uniqueness, and adds the superadmin endpoints + frontend header.
    """

    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(63), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    custom_domain: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
