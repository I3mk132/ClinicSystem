from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    name_ar: str = Field(min_length=2, max_length=150)
    name_tr: str = Field(min_length=2, max_length=150)
    description_ar: Optional[str] = None
    description_tr: Optional[str] = None
    icon: str = "stethoscope"
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_tr: Optional[str] = None
    description_ar: Optional[str] = None
    description_tr: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None


class DepartmentOut(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
