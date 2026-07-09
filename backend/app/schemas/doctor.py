from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.department import DepartmentOut


class DoctorBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    title_ar: Optional[str] = None
    title_tr: Optional[str] = None
    bio_ar: Optional[str] = None
    bio_tr: Optional[str] = None
    photo_url: Optional[str] = None
    department_id: int
    is_active: bool = True


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(BaseModel):
    full_name: Optional[str] = None
    title_ar: Optional[str] = None
    title_tr: Optional[str] = None
    bio_ar: Optional[str] = None
    bio_tr: Optional[str] = None
    photo_url: Optional[str] = None
    department_id: Optional[int] = None
    is_active: Optional[bool] = None


class DoctorOut(DoctorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department: Optional[DepartmentOut] = None
