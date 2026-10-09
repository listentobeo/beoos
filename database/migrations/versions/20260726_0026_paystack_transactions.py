"""Add provider-verified Paystack transactions and webhook events.

Revision ID: 20260726_0026
Revises: 20260726_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0026"
down_revision: str | None = "20260726_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quote_id",
            UUID,
            sa.ForeignKey("quotes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_reference", sa.String(160), nullable=False),
        sa.Column("provider_transaction_id", sa.String(160)),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("provider_status", sa.String(60)),
        sa.Column("authorization_url", sa.Text()),
        sa.Column("channel", sa.String(60)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("outcome_id", UUID, sa.ForeignKey("outcomes.id")),
        *_timestamps(),
        sa.UniqueConstraint(
            "provider", "provider_reference", name="uq_payment_provider_reference"
        ),
        sa.CheckConstraint(
            "status IN ('pending','confirmed','failed','cancelled','reversed')",
            name="ck_payment_transaction_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_payment_transaction_amount"),
    )
    op.create_index(
        "ix_payment_transactions_business_status",
        "payment_transactions",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_payment_transactions_quote", "payment_transactions", ["quote_id"]
    )
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_transaction_id",
            UUID,
            sa.ForeignKey("payment_transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload_hash", sa.String(96), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("provider", "event_key", name="uq_payment_webhook_event"),
        sa.CheckConstraint(
            "status IN ('processing','processed','rejected')",
            name="ck_payment_webhook_status",
        ),
    )
    op.create_index(
        "ix_payment_webhook_events_business_created",
        "payment_webhook_events",
        ["business_id", "created_at"],
    )
    for table in ("payment_transactions", "payment_webhook_events"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE POLICY beoos_tenant_access ON {table} FOR ALL "
                "USING (beoos_can_access_business(business_id)) "
                "WITH CHECK (beoos_can_access_business(business_id))"
            )
        )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_payment_tenant()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_TABLE_NAME = 'payment_transactions' THEN
                    IF (
                    NOT EXISTS (
                        SELECT 1 FROM quotes
                        WHERE id = NEW.quote_id AND business_id = NEW.business_id
                    ) OR NOT EXISTS (
                        SELECT 1 FROM workflow_runs
                        WHERE id = NEW.workflow_run_id AND business_id = NEW.business_id
                    )
                    ) THEN RAISE EXCEPTION 'cross-tenant payment reference';
                    END IF;
                ELSIF TG_TABLE_NAME = 'payment_webhook_events' THEN
                    IF NOT EXISTS (
                    SELECT 1 FROM payment_transactions
                    WHERE id = NEW.payment_transaction_id
                      AND business_id = NEW.business_id
                    ) THEN RAISE EXCEPTION 'cross-tenant payment webhook';
                    END IF;
                END IF;
                RETURN NEW;
            END; $$;
            """
        )
    )
    for table in ("payment_transactions", "payment_webhook_events"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table}_tenant_integrity "
                f"BEFORE INSERT OR UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION beoos_assert_payment_tenant()"
            )
        )


def downgrade() -> None:
    for table in ("payment_transactions", "payment_webhook_events"):
        op.execute(
            sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_tenant_integrity ON {table}")
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_payment_tenant()"))
    op.drop_table("payment_webhook_events")
    op.drop_table("payment_transactions")
