"""Repair shared tenant triggers for tables with different record fields.

Revision ID: 20261009_0029
Revises: 20260729_0028

Table selection must happen before PostgreSQL resolves table-specific NEW fields.
Replace the functions for databases that already applied the earlier revisions.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_0029"
down_revision: str | None = "20260729_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_workflow_tenant()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE related_business_id uuid;
            BEGIN
                IF TG_TABLE_NAME = 'workflow_runs' THEN
                    SELECT business_id INTO related_business_id
                    FROM workflow_definitions WHERE id = NEW.workflow_definition_id;
                    IF related_business_id IS NOT NULL
                       AND related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant workflow definition';
                    END IF;
                ELSIF TG_TABLE_NAME IN (
                    'workflow_steps','ai_executions','tool_calls','approval_requests',
                    'human_corrections','outcomes'
                ) THEN
                    SELECT business_id INTO related_business_id
                    FROM workflow_runs WHERE id = NEW.workflow_run_id;
                    IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant workflow run relationship';
                    END IF;
                    IF TG_TABLE_NAME = 'approval_requests' THEN
                        IF NEW.affected_customer_id IS NOT NULL THEN
                            SELECT business_id INTO related_business_id
                            FROM contacts WHERE id = NEW.affected_customer_id;
                            IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                                RAISE EXCEPTION 'cross-tenant approval customer';
                            END IF;
                        END IF;
                    END IF;
                ELSIF TG_TABLE_NAME = 'tool_permissions'
                      AND NEW.workflow_definition_id IS NOT NULL THEN
                    SELECT business_id INTO related_business_id
                    FROM workflow_definitions WHERE id = NEW.workflow_definition_id;
                    IF related_business_id IS NULL
                       OR related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant tool permission workflow';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_operator_tenant()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_TABLE_NAME = 'operator_messages' THEN
                    IF NOT EXISTS (
                    SELECT 1 FROM operator_conversations
                    WHERE id = NEW.conversation_id AND business_id = NEW.business_id
                    ) THEN RAISE EXCEPTION 'cross-tenant operator conversation';
                    END IF;
                ELSIF TG_TABLE_NAME = 'operator_turns' THEN
                    IF (
                    NOT EXISTS (
                        SELECT 1 FROM operator_conversations
                        WHERE id = NEW.conversation_id AND business_id = NEW.business_id
                    ) OR NOT EXISTS (
                        SELECT 1 FROM operator_messages
                        WHERE id = NEW.user_message_id
                          AND conversation_id = NEW.conversation_id
                          AND business_id = NEW.business_id
                    ) OR (
                        NEW.assistant_message_id IS NOT NULL AND NOT EXISTS (
                            SELECT 1 FROM operator_messages
                            WHERE id = NEW.assistant_message_id
                              AND conversation_id = NEW.conversation_id
                              AND business_id = NEW.business_id
                        )
                    )
                    ) THEN RAISE EXCEPTION 'invalid operator turn provenance';
                    END IF;
                END IF;
                RETURN NEW;
            END; $$;
            """
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


def downgrade() -> None:
    # These function bodies remain compatible with the previous schema. Keep the
    # corrected guards on rollback rather than restoring known runtime failures.
    pass
