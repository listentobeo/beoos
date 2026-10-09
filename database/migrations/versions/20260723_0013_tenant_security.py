"""Enforce tenant RLS coverage and cross-tenant relationship integrity.

Revision ID: 20260723_0013
Revises: 20260719_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0013"
down_revision: str | None = "20260719_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIRECT_TENANT_TABLES = (
    "business_members",
    "mailbox_connections",
    "contacts",
    "email_threads",
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
    "external_api_tokens",
)

ALL_TENANT_TABLES = (
    "businesses",
    *DIRECT_TENANT_TABLES,
    "email_messages",
    "email_analyses",
    "email_drafts",
    "whatsapp_webhook_events",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_request_user_id()
            RETURNS text
            LANGUAGE sql
            STABLE
            AS $$
                SELECT NULLIF(
                    NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub',
                    ''
                )
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_can_access_business(target_business_id uuid)
            RETURNS boolean
            LANGUAGE sql
            STABLE
            SECURITY DEFINER
            SET search_path = public
            AS $$
                SELECT EXISTS (
                    SELECT 1
                    FROM business_members
                    WHERE business_id = target_business_id
                      AND clerk_user_id = beoos_request_user_id()
                )
            $$;
            """
        )
    )

    for table_name in ALL_TENANT_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))

    _policy("businesses", "beoos_can_access_business(id)")
    for table_name in DIRECT_TENANT_TABLES:
        _policy(table_name, "beoos_can_access_business(business_id)")
    _policy(
        "email_messages",
        "EXISTS (SELECT 1 FROM email_threads t "
        "WHERE t.id = email_messages.thread_id AND beoos_can_access_business(t.business_id))",
    )
    _policy(
        "email_analyses",
        "EXISTS (SELECT 1 FROM email_messages m JOIN email_threads t ON t.id = m.thread_id "
        "WHERE m.id = email_analyses.message_id AND beoos_can_access_business(t.business_id))",
    )
    _policy(
        "email_drafts",
        "EXISTS (SELECT 1 FROM email_threads t "
        "WHERE t.id = email_drafts.thread_id AND beoos_can_access_business(t.business_id))",
    )
    _policy(
        "whatsapp_webhook_events",
        "business_id IS NOT NULL AND beoos_can_access_business(business_id)",
    )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_tenant_relationships()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                related_business_id uuid;
                second_business_id uuid;
            BEGIN
                IF TG_TABLE_NAME = 'email_threads' THEN
                    IF NEW.contact_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id
                        FROM contacts WHERE id = NEW.contact_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant email_threads.contact_id';
                        END IF;
                    END IF;
                ELSIF TG_TABLE_NAME = 'email_messages' THEN
                    SELECT business_id INTO related_business_id FROM email_threads WHERE id = NEW.thread_id;
                    SELECT business_id INTO second_business_id FROM mailbox_connections WHERE id = NEW.mailbox_id;
                    IF related_business_id IS NULL OR second_business_id IS NULL
                       OR related_business_id IS DISTINCT FROM second_business_id THEN
                        RAISE EXCEPTION 'cross-tenant email message relationship';
                    END IF;
                ELSIF TG_TABLE_NAME = 'crm_leads' THEN
                    IF NEW.contact_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id FROM contacts WHERE id = NEW.contact_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant crm_leads.contact_id';
                        END IF;
                    END IF;
                    IF NEW.thread_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id FROM email_threads WHERE id = NEW.thread_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant crm_leads.thread_id';
                        END IF;
                    END IF;
                ELSIF TG_TABLE_NAME = 'follow_up_tasks' THEN
                    SELECT business_id INTO related_business_id FROM crm_leads WHERE id = NEW.lead_id;
                    IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant follow_up_tasks.lead_id';
                    END IF;
                    IF NEW.thread_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id FROM email_threads WHERE id = NEW.thread_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant follow_up_tasks.thread_id';
                        END IF;
                    END IF;
                    IF NEW.contact_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id FROM contacts WHERE id = NEW.contact_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant follow_up_tasks.contact_id';
                        END IF;
                    END IF;
                ELSIF TG_TABLE_NAME = 'quotes' THEN
                    IF NEW.template_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id FROM quote_templates WHERE id = NEW.template_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant quotes.template_id';
                        END IF;
                    END IF;
                    IF NEW.lead_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id FROM crm_leads WHERE id = NEW.lead_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant quotes.lead_id';
                        END IF;
                    END IF;
                    IF NEW.contact_id IS NOT NULL THEN
                        SELECT business_id INTO related_business_id FROM contacts WHERE id = NEW.contact_id;
                        IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                            RAISE EXCEPTION 'cross-tenant quotes.contact_id';
                        END IF;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )

    for table_name in ("email_threads", "email_messages", "crm_leads", "follow_up_tasks", "quotes"):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table_name}_tenant_integrity
                BEFORE INSERT OR UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION beoos_assert_tenant_relationships()
                """
            )
        )


def downgrade() -> None:
    for table_name in ("email_threads", "email_messages", "crm_leads", "follow_up_tasks", "quotes"):
        op.execute(
            sa.text(f"DROP TRIGGER IF EXISTS trg_{table_name}_tenant_integrity ON {table_name}")
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_tenant_relationships()"))
    for table_name in ALL_TENANT_TABLES:
        op.execute(sa.text(f'DROP POLICY IF EXISTS beoos_tenant_access ON "{table_name}"'))
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_can_access_business(uuid)"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_request_user_id()"))


def _policy(table_name: str, expression: str) -> None:
    op.execute(sa.text(f'DROP POLICY IF EXISTS beoos_tenant_access ON "{table_name}"'))
    op.execute(
        sa.text(
            f'CREATE POLICY beoos_tenant_access ON "{table_name}" '
            f"FOR ALL USING ({expression}) WITH CHECK ({expression})"
        )
    )
