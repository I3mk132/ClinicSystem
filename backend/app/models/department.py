from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Department(Base):
    """
    A medical department / specialty (e.g. Dentistry, Dermatology).
    Bilingual fields (ar / tr) so the clinic name & content can be
    customized per language without extra tables.
    """

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Tenant owner. Nullable during the Session 2 split; 2b -> NOT NULL + name unique per clinic.
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=True)
    name_ar: Mapped[str] = mapped_column(String(150), nullable=False)
    name_tr: Mapped[str] = mapped_column(String(150), nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, nullable=True)
    description_tr: Mapped[str] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="stethoscope")  # icon key used by the frontend
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    doctors = relationship("Doctor", back_populates="department")
