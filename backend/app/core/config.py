"""
Central application configuration.

Everything that might change between environments (dev / staging / production)
or between deployments (different clinic, different database, different domain)
lives here and is read from environment variables (see .env.example).

This is the ONLY file that should read os.environ directly - every other
module should import `settings` from here.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    APP_NAME: str = "Clinic Booking System"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    # --- Security ---
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # --- Database ---
    # Swap this single value to move from SQLite -> PostgreSQL / MySQL later.
    DATABASE_URL: str = "sqlite:///./clinic.db"

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"

    # --- Default admin (created by seed script) ---
    FIRST_ADMIN_EMAIL: str = "admin@myclinic.com"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"
    FIRST_ADMIN_NAME: str = "Clinic Administrator"

    # --- Seeding ---
    # Demo departments/doctors/API key (python -m app.seed). Set to false in
    # production so a fresh deploy starts with only the admin account.
    SEED_DEMO_DATA: bool = True

    # --- Verification codes (account verification / forgot password) ---
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6

    # --- Email provider: "console" (default, just logs) or "smtp" ---
    EMAIL_PROVIDER: str = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM_ADDRESS: str = "no-reply@myclinic.com"
    EMAIL_FROM_NAME: str = "Clinic Booking System"

    # --- SMS provider: "console" (default, just logs) or "twilio" ---
    SMS_PROVIDER: str = "console"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def model_post_init(self, __context) -> None:
        # Refuse to boot a production deployment signing JWTs with the
        # publicly-known default secret - anyone could forge admin tokens.
        insecure_defaults = {"insecure-dev-secret-change-me", "change-this-to-a-long-random-secret-key"}
        if self.ENVIRONMENT.lower() == "production" and self.SECRET_KEY in insecure_defaults:
            raise RuntimeError(
                "SECRET_KEY is still the insecure default while ENVIRONMENT=production. "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance - import this everywhere instead of re-reading env vars."""
    return Settings()


settings = get_settings()
