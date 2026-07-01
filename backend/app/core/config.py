from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "BeoOS API"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/beoos"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    secret_encryption_key: str = ""

    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    bootstrap_clerk_user_id: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-5.5"

    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_accounts_base_url: str = "https://accounts.zoho.com"
    zoho_mail_base_url: str = "https://mail.zoho.com"

    resend_api_key: str = ""
    alert_from_email: str = "alerts@beoarts.com"
    cors_origins: list[str] = Field(default_factory=list)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return self.cors_origins or [str(self.frontend_url).rstrip("/")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
