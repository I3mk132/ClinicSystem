"""
Per-clinic theming (Session 3).

Two layers make up a clinic's look:

  1. A developer-controlled PRESET (JSON file in app/themes/). It holds the big
     decisions - font family/imports, the full colour palette, border radius,
     layout density. Only the developer edits these files, and only the
     superadmin switches which preset a clinic uses (clinic.theme_preset).

  2. The admin-editable OVERRIDES layer (clinic.theme_overrides, a JSON column).
     A clinic admin can tweak a small, safe subset - the primary/secondary/accent
     colours, the logo, and the display name + hero/contact/footer texts (per
     language) - via the Theme panel.

`effective_theme(clinic)` merges preset + overrides into the single object the
public GET /api/v1/public/theme endpoint returns and the frontend applies as CSS
custom properties. The preset is the source of truth for everything the admin is
NOT allowed to touch, so a broken/empty overrides blob still yields a valid theme.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

from app.models.clinic import Clinic

_THEMES_DIR = Path(__file__).parent / "themes"
DEFAULT_PRESET = "default"

# Colour keys the admin overrides layer is allowed to change (they map 1:1 to
# CSS custom properties --color-<key>). Everything else in the palette - the
# derived shades, backgrounds, text/border colours - stays owned by the preset.
ADMIN_COLOR_KEYS = ("primary", "secondary", "accent")


def _load_presets() -> Dict[str, Dict[str, Any]]:
    presets: Dict[str, Dict[str, Any]] = {}
    for path in sorted(_THEMES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            presets[path.stem] = json.load(f)
    return presets


# Loaded once at import. Presets are static files shipped with the app, so
# there's no need to re-read them per request.
PRESETS: Dict[str, Dict[str, Any]] = _load_presets()


def preset_names() -> List[str]:
    return list(PRESETS.keys())


def get_preset(name: str) -> Dict[str, Any]:
    """Return a deep copy of a preset, falling back to the default if unknown."""
    preset = PRESETS.get(name) or PRESETS.get(DEFAULT_PRESET)
    if preset is None:  # no preset files at all - should never happen in a real deploy
        return {"fonts": {}, "colors": {}, "radius": {}, "density": "comfortable"}
    return copy.deepcopy(preset)


def _lang_pair(value: Any, fallback: str = "") -> Dict[str, str]:
    """Normalise an {ar, tr} text field, filling blanks with `fallback`."""
    value = value if isinstance(value, dict) else {}
    return {
        "ar": (value.get("ar") or fallback or "").strip() if isinstance(value.get("ar"), str) else fallback,
        "tr": (value.get("tr") or fallback or "").strip() if isinstance(value.get("tr"), str) else fallback,
    }


def effective_theme(clinic: Clinic) -> Dict[str, Any]:
    """Merge the clinic's preset with its admin overrides into the served theme."""
    preset = get_preset(clinic.theme_preset)
    overrides = clinic.theme_overrides if isinstance(clinic.theme_overrides, dict) else {}

    # Colours: preset palette is the base; the admin may override only the three
    # brand colours, and only with sensibly-shaped string values.
    colors = dict(preset.get("colors", {}))
    ov_colors = overrides.get("colors") if isinstance(overrides.get("colors"), dict) else {}
    for key in ADMIN_COLOR_KEYS:
        val = ov_colors.get(key)
        if isinstance(val, str) and val.strip():
            colors[key] = val.strip()

    return {
        "preset": clinic.theme_preset,
        "label": preset.get("label", clinic.theme_preset),
        "fonts": preset.get("fonts", {}),
        "colors": colors,
        "radius": preset.get("radius", {}),
        "density": preset.get("density", "comfortable"),
        "logo_url": (overrides.get("logo_url") or "").strip() if isinstance(overrides.get("logo_url"), str) else "",
        "name": _lang_pair(overrides.get("name"), fallback=clinic.name),
        "hero": {
            "title": _lang_pair((overrides.get("hero") or {}).get("title")),
            "subtitle": _lang_pair((overrides.get("hero") or {}).get("subtitle")),
        },
        "contact": {
            "phone": (overrides.get("contact") or {}).get("phone", "") if isinstance(overrides.get("contact"), dict) else "",
            "address": _lang_pair((overrides.get("contact") or {}).get("address")),
        },
        "footer": _lang_pair(overrides.get("footer")),
        # Web chat widget (Session 6). Enabled unless the admin explicitly
        # stored False, so a fresh clinic gets the bot by default.
        "chatbot_enabled": overrides.get("chatbot_enabled") is not False,
    }
