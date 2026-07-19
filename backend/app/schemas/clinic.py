from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClinicCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=63, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
                      description="URL-safe tenant id, e.g. 'smile-dental'")
    name: str = Field(min_length=2, max_length=150)
    custom_domain: Optional[str] = Field(default=None, max_length=255)


class ClinicUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    custom_domain: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class ClinicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    custom_domain: Optional[str] = None
    is_active: bool
    created_at: datetime


class ClinicAdminCreate(BaseModel):
    """Create the first clinic-admin user for a clinic (superadmin action)."""

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    preferred_language: str = Field(default="ar", pattern="^(ar|tr)$")
