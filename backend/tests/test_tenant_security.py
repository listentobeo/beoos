from pathlib import Path

from app.core.config import Settings
from app.infrastructure.models import Business
from app.services.whatsapp import WhatsAppCloudService

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "versions" / "20260723_0013_tenant_security.py"


def test_security_migration_covers_every_tenant_owned_table() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    required = {
        "businesses",
        "business_members",
        "mailbox_connections",
        "contacts",
        "email_threads",
        "email_messages",
        "email_analyses",
        "email_drafts",
        "price_catalog_items",
        "audit_logs",
        "push_subscriptions",
        "crm_leads",
        "follow_up_tasks",
        "quote_templates",
        "quotes",
        "marketing_metrics",
        "whatsapp_connections",
        "whatsapp_signup_attempts",
        "whatsapp_webhook_events",
        "external_api_tokens",
    }
    for table_name in required:
        assert f'"{table_name}"' in migration or f"'{table_name}'" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "beoos_tenant_access" in migration


def test_cross_tenant_relationship_triggers_are_declared() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TRIGGER trg_{table_name}_tenant_integrity" in migration
    for table_name in ("email_threads", "email_messages", "crm_leads", "follow_up_tasks", "quotes"):
        assert f'"{table_name}"' in migration


def test_production_whatsapp_never_uses_global_credentials() -> None:
    settings = Settings(
        app_env="production",
        whatsapp_access_token="global-secret",
        whatsapp_phone_number_id="global-phone",
        allow_nonproduction_global_whatsapp_fallback=True,
    )
    business = Business(
        slug="tenant",
        name="Tenant",
        primary_email="owner@example.com",
        whatsapp_number="+2348000000000",
        reply_signature="Owner",
        settings={},
    )
    service = WhatsAppCloudService(settings)
    assert service.access_token_for(business) == ""
    assert service.phone_number_id_for(business) == ""


def test_development_fallback_requires_explicit_flag() -> None:
    business = Business(
        slug="tenant",
        name="Tenant",
        primary_email="owner@example.com",
        whatsapp_number="+2348000000000",
        reply_signature="Owner",
        settings={},
    )
    disabled = WhatsAppCloudService(
        Settings(
            app_env="development",
            whatsapp_access_token="global-secret",
            whatsapp_phone_number_id="global-phone",
        )
    )
    enabled = WhatsAppCloudService(
        Settings(
            app_env="development",
            whatsapp_access_token="global-secret",
            whatsapp_phone_number_id="global-phone",
            allow_nonproduction_global_whatsapp_fallback=True,
        )
    )
    assert disabled.access_token_for(business) == ""
    assert enabled.access_token_for(business) == "global-secret"
    assert enabled.phone_number_id_for(business) == "global-phone"
