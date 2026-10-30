import re
import sys
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 4000
    NODE_ENV: Literal["development", "production", "test"] = "development"
    DATABASE_URL: str
    JWT_SECRET: str = Field(min_length=32)
    MFA_ENCRYPTION_KEY: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    UPLOAD_DIR: str = "uploads"
    MFA_ISSUER: str = "HospitalManagement"
    # Stripe is optional: without a secret key the payment endpoints answer 503.
    STRIPE_SECRET_KEY: str | None = Field(default=None, pattern=r"^sk_")
    STRIPE_WEBHOOK_SECRET: str | None = Field(default=None, pattern=r"^whsec_")
    STRIPE_CURRENCY: str = Field(default="inr", min_length=3, max_length=3)
    # Where Stripe sends the browser after checkout.
    FRONTEND_URL: str = "http://localhost:3000"
    SUPER_ADMIN_EMAIL: str | None = None
    SUPER_ADMIN_PASSWORD: str | None = Field(default=None, min_length=10)
    SUPER_ADMIN_NAME: str = "Super Admin"

    @field_validator("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "SUPER_ADMIN_EMAIL", "SUPER_ADMIN_PASSWORD", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return None if v == "" else v

    @field_validator("STRIPE_CURRENCY")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

    @property
    def async_database_url(self) -> str:
        """SQLAlchemy/asyncpg URL; drops query params like ?schema=public that asyncpg does not understand."""
        parts = urlsplit(self.DATABASE_URL)
        return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, "", ""))


try:
    settings = Settings()  # type: ignore[call-arg]
except Exception as e:  # noqa: BLE001
    print(f"Invalid environment:\n{e}", file=sys.stderr)
    sys.exit(1)

# The all-zeros MFA key from .env.example is public knowledge: fine for local dev, never for real data.
if re.fullmatch(r"0+", settings.MFA_ENCRYPTION_KEY):
    if settings.NODE_ENV == "production":
        print("MFA_ENCRYPTION_KEY is the all-zeros placeholder. Generate one with: openssl rand -hex 32", file=sys.stderr)
        sys.exit(1)
    print("⚠ MFA_ENCRYPTION_KEY is the all-zeros placeholder (ok for local dev only). See README: key rotation.")
