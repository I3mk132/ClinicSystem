from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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
    theme_preset: str
    created_at: datetime


class ClinicAdminCreate(BaseModel):
    """Create the first clinic-admin user for a clinic (superadmin action)."""

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    preferred_language: str = Field(default="ar", pattern="^(ar|tr)$")


# --- Theming (Session 3) ----------------------------------------------------

_HEX = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class LangText(BaseModel):
    """An {ar, tr} text pair (both optional)."""

    ar: Optional[str] = Field(default=None, max_length=2000)
    tr: Optional[str] = Field(default=None, max_length=2000)


class ThemeColorsIn(BaseModel):
    """The only three palette colours a clinic admin may override."""

    primary: Optional[str] = Field(default=None, pattern=_HEX)
    secondary: Optional[str] = Field(default=None, pattern=_HEX)
    accent: Optional[str] = Field(default=None, pattern=_HEX)


class ThemeContactIn(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[LangText] = None


class ThemeHeroIn(BaseModel):
    title: Optional[LangText] = None
    subtitle: Optional[LangText] = None


class ThemeOverridesIn(BaseModel):
    """
    Admin-editable theme layer (PUT /admin/theme). Everything is optional; the
    stored blob is merged on top of the developer preset. `model_dump(exclude_none)`
    keeps the persisted overrides sparse. Colours are hex-validated and the logo
    URL is constrained so neither can smuggle CSS/markup into the frontend.
    """

    model_config = ConfigDict(extra="forbid")

    colors: Optional[ThemeColorsIn] = None
    logo_url: Optional[str] = Field(default=None, max_length=500)
    name: Optional[LangText] = None
    hero: Optional[ThemeHeroIn] = None
    contact: Optional[ThemeContactIn] = None
    footer: Optional[LangText] = None

    @field_validator("logo_url")
    @classmethod
    def _validate_logo(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not (v.startswith("https://") or v.startswith("http://") or v.startswith("/") or v.startswith("assets/")):
            raise ValueError("logo_url must be an http(s) URL or a relative asset path")
        return v


class ClinicPresetUpdate(BaseModel):
    """Superadmin: switch a clinic's developer preset."""

    theme_preset: str = Field(min_length=1, max_length=50)


class AdminThemeOut(BaseModel):
    """What the admin Theme panel loads: current preset, raw overrides, and the
    merged effective theme (for live preview)."""

    preset: str
    available_presets: list[str]
    overrides: Dict[str, Any]
    effective: Dict[str, Any]
