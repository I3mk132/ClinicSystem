from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import ContactMethod, UserRole


class UserBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    preferred_language: str = Field(default="ar", pattern="^(ar|tr)$")
    contact_method: ContactMethod = ContactMethod.EMAIL


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _validate_contact(self):
        if self.contact_method == ContactMethod.EMAIL and not self.email:
            raise ValueError("Email is required when contact_method is 'email'")
        if self.contact_method == ContactMethod.PHONE and not self.phone:
            raise ValueError("Phone is required when contact_method is 'phone'")
        if not self.email and not self.phone:
            raise ValueError("Provide at least an email or a phone number")
        return self


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    phone: Optional[str] = None
    preferred_language: Optional[str] = Field(default=None, pattern="^(ar|tr)$")


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
