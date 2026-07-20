"""
Bot service configuration - the ONLY module that reads env vars.

The bot is a standalone service: it never imports from backend/app and never
touches the clinic database. Its only access to clinic data is the public REST
API (/api/v1/public/*), authenticated per clinic with that clinic's X-API-Key.

Tenant registry: each clinic the bot serves has an entry mapping a public
"tenant" id (what the web client sends) to that clinic's API key. Provisioning:
  1) the clinic admin creates an API key in the admin panel (as today),
  2) the developer adds a `tenant:key` pair to BOT_TENANTS.

BOT_TENANTS format: comma-separated `tenant=apikey` pairs, e.g.
  BOT_TENANTS="default=ck_live_abc123,acme=ck_live_def456"
"""
from functools import lru_cache
from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where the clinic backend's public API lives (no trailing slash).
    CLINIC_API_BASE_URL: str = "http://127.0.0.1:8000/api/v1"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # tenant -> clinic API key
    BOT_TENANTS: str = ""

    # CORS origins for the web chat widget (comma-separated, exact origins)
    CORS_ORIGINS: str = "*"

    # Safety rails
    MAX_MESSAGE_CHARS: int = 1000
    RATE_LIMIT_PER_MINUTE: int = 20
    CONVERSATION_TTL_SECONDS: int = 3600
    MAX_TOOL_ITERATIONS: int = 6
    MAX_HISTORY_TURNS: int = 20

    @property
    def tenants(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for pair in self.BOT_TENANTS.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            tenant, key = pair.split("=", 1)
            tenant, key = tenant.strip(), key.strip()
            if tenant and key:
                out[tenant] = key
        return out

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.GEMINI_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
