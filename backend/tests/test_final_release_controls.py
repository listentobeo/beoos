from pathlib import Path

from cryptography.fernet import Fernet

from app.infrastructure.models import Base, MailboxConnection, WhatsAppConnection
from app.services.crypto import SecretCipher

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "migrations" / "versions"


def test_every_business_id_table_is_declared_in_an_rls_migration() -> None:
    migration_sources = [
        path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.py"))
    ]
    tenant_tables = {
        table.name for table in Base.metadata.tables.values() if "business_id" in table.c
    }

    uncovered = {
        table_name
        for table_name in tenant_tables
        if not any(
            table_name in source and "ENABLE ROW LEVEL SECURITY" in source
            for source in migration_sources
        )
    }

    assert not uncovered, f"Tenant tables missing an RLS migration: {sorted(uncovered)}"


def test_connector_credentials_use_encrypted_storage_and_round_trip() -> None:
    assert "access_token" not in MailboxConnection.__table__.c
    assert "refresh_token" not in MailboxConnection.__table__.c
    assert "access_token_encrypted" in MailboxConnection.__table__.c
    assert "refresh_token_encrypted" in MailboxConnection.__table__.c
    assert "access_token" not in WhatsAppConnection.__table__.c
    assert "access_token_encrypted" in WhatsAppConnection.__table__.c

    cipher = SecretCipher(Fernet.generate_key().decode())
    plaintext = "provider-secret"
    ciphertext = cipher.encrypt(plaintext)

    assert ciphertext != plaintext
    assert cipher.decrypt(ciphertext) == plaintext
