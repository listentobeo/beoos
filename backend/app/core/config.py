import json
from functools import lru_cache
from typing import Literal

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

    meta_app_secret: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""
    whatsapp_graph_base_url: str = "https://graph.facebook.com/v20.0"

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@beoarts.com"

    resend_api_key: str = ""
    alert_from_email: str = "beoos@alerts.beoarts.com"
    cors_origins: str = ""

    @property
    def allowed_origins(self) -> list[str]:
        value = self.cors_origins.strip()
        if not value:
            return [str(self.frontend_url).rstrip("/")]
        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list):
                return [str(origin).strip().rstrip("/") for origin in parsed if str(origin).strip()]
        return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
