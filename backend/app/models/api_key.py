from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiKey(Base):
    """
    A key issued by the clinic admin to a trusted integration (the main
    hospital/clinic system, a WhatsApp bot, a Telegram bot, ...). Sent as
    the `X-API-Key` header on every request to the /api/v1/public/* routes
    (see routers/public.py, dependencies.get_api_key).

    Only the SHA-256 hash of the key is stored - the raw key is shown to
    the admin exactly once, at creation time, exactly like a typical
    third-party API key UX (Stripe, GitHub tokens, etc).
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # The clinic this key belongs to. Public /api/v1/public/* routes resolve the
    # tenant from the KEY (never from a header) - a key must never read another
    # clinic's data.
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)  # e.g. "Telegram Bot", "Main HIS"
    hashed_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)  # shown in the UI so admins can tell keys apart

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
