"""Persist tenant operator conversations and bounded execution traces.

Revision ID: 20260726_0024
Revises: 20260726_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0024"
down_revision: str | None = "20260726_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "operator_conversations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('active','archived')", name="ck_operator_conversation_status"
        ),
    )
    op.create_index(
        "ix_operator_conversations_business_updated",
        "operator_conversations",
        ["business_id", "updated_at"],
    )
    op.create_index(
        "ix_operator_conversations_user",
        "operator_conversations",
        ["business_id", "user_id"],
    )
    op.create_table(
        "operator_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            UUID,
            sa.ForeignKey("operator_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("grounding_sources", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("statement_labels", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tool_activity", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("authoritative", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role IN ('user','operator')", name="ck_operator_message_role"),
        sa.CheckConstraint("NOT authoritative", name="ck_operator_history_not_authoritative"),
    )
    op.create_index(
        "ix_operator_messages_conversation_created",
        "operator_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_operator_messages_business_created",
        "operator_messages",
        ["business_id", "created_at"],
    )
    op.create_table(
        "operator_turns",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            UUID,
            sa.ForeignKey("operator_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_message_id",
            UUID,
            sa.ForeignKey("operator_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assistant_message_id",
            UUID,
            sa.ForeignKey("operator_messages.id", ondelete="SET NULL"),
        ),
        sa.Column("selected_tools", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_tool_calls", sa.Integer(), nullable=False),
        sa.Column("loop_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("loop_limit", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("cost_limit", sa.Numeric(14, 6), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "tool_call_count >= 0 AND tool_call_count <= max_tool_calls",
            name="ck_operator_tool_budget",
        ),
        sa.CheckConstraint(
            "loop_count > 0 AND loop_count <= loop_limit",
            name="ck_operator_loop_budget",
        ),
        sa.CheckConstraint(
            "estimated_cost >= 0 AND estimated_cost <= cost_limit",
            name="ck_operator_cost_budget",
        ),
        sa.CheckConstraint(
            "status IN ('completed','fallback','failed')", name="ck_operator_turn_status"
        ),
    )
    op.create_index(
        "ix_operator_turns_business_created",
        "operator_turns",
        ["business_id", "created_at"],
    )
    op.create_index(
        "ix_operator_turns_conversation",
        "operator_turns",
        ["conversation_id"],
    )
    for table in ("operator_conversations", "operator_messages", "operator_turns"):
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
            CREATE OR REPLACE FUNCTION beoos_assert_operator_tenant()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_TABLE_NAME = 'operator_messages' AND NOT EXISTS (
                    SELECT 1 FROM operator_conversations
                    WHERE id = NEW.conversation_id AND business_id = NEW.business_id
                ) THEN RAISE EXCEPTION 'cross-tenant operator conversation';
                ELSIF TG_TABLE_NAME = 'operator_turns' AND (
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
                RETURN NEW;
            END; $$;
            """
        )
    )
    for table in ("operator_messages", "operator_turns"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table}_tenant_integrity "
                f"BEFORE INSERT OR UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION beoos_assert_operator_tenant()"
            )
        )


def downgrade() -> None:
    for table in ("operator_messages", "operator_turns"):
        op.execute(
            sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_tenant_integrity ON {table}")
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_operator_tenant()"))
    op.drop_table("operator_turns")
    op.drop_table("operator_messages")
    op.drop_table("operator_conversations")
