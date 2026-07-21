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
    ai_provider: Literal["openai", "replicate"] = "openai"
    replicate_api_token: str = ""
    replicate_model: str = "openai/gpt-5.4"
    replicate_timeout_seconds: int = 90
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    ai_quote_provider: Literal["auto", "openai", "replicate", "anthropic"] = "auto"
    microsoft_clarity_api_token: str = ""
    microsoft_clarity_base_url: str = "https://www.clarity.ms"

    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_accounts_base_url: str = "https://accounts.zoho.com"
    zoho_mail_base_url: str = "https://mail.zoho.com"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_accounts_base_url: str = "https://accounts.google.com"
    google_token_url: str = "https://oauth2.googleapis.com/token"
    google_userinfo_url: str = "https://openidconnect.googleapis.com/v1/userinfo"
    google_gmail_base_url: str = "https://gmail.googleapis.com"

    meta_app_secret: str = ""
    meta_app_id: str = ""
    meta_whatsapp_config_id: str = ""
    meta_whatsapp_coexistence_config_id: str = ""
    meta_whatsapp_cloud_config_id: str = ""
    whatsapp_coexistence_enabled: bool = False
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""
    whatsapp_graph_base_url: str = "https://graph.facebook.com/v20.0"

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@beoarts.com"

    mailbox_auto_sync_enabled: bool = True
    mailbox_auto_sync_interval_seconds: int = 60
    mailbox_auto_sync_batch_size: int = 10
    mailbox_auto_sync_lease_minutes: int = 5
    follow_up_scheduler_enabled: bool = True
    follow_up_scheduler_interval_seconds: int = 60
    follow_up_scheduler_batch_size: int = 10
    daily_report_scheduler_enabled: bool = True
    daily_report_scheduler_interval_seconds: int = 300
    daily_report_scheduler_batch_size: int = 25

    resend_api_key: str = ""
    alert_from_email: str = "beoos@alerts.beoarts.com"
    sms_provider: str = ""
    sms_api_key: str = ""
    sms_from: str = ""
    cors_origins: str = ""

    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""

    @property
    def effective_ai_provider(self) -> Literal["openai", "replicate"]:
        if self.ai_provider == "replicate":
            return "replicate"
        if self.replicate_api_token and not self.openai_api_key:
            return "replicate"
        return "openai"

    @property
    def ai_configured(self) -> bool:
        if self.effective_ai_provider == "replicate":
            return bool(self.replicate_api_token)
        return bool(self.openai_api_key)

    @property
    def effective_ai_model(self) -> str:
        if self.effective_ai_provider == "replicate":
            return f"replicate:{self.replicate_model}"
        return self.openai_model

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
