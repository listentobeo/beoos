"""Add progressive onboarding and workflow discovery.

Revision ID: 20260723_0017
Revises: 20260723_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0017"
down_revision: str | None = "20260723_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "onboarding_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("onboarding_stage", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="in_progress"),
        sa.Column("completion_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_first_problem", sa.String(120)),
        sa.Column("current_question_key", sa.String(160)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("draft_specification", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("activation_confirmed_by", sa.String(255)),
        sa.Column("activation_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("deployment_mode", sa.String(40), nullable=False, server_default="experimental"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "onboarding_stage BETWEEN 1 AND 10", name="ck_onboarding_session_stage"
        ),
        sa.CheckConstraint(
            "completion_percentage BETWEEN 0 AND 100",
            name="ck_onboarding_session_completion",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress','ready_for_preview','awaiting_activation',"
            "'completed','abandoned')",
            name="ck_onboarding_session_status",
        ),
        sa.CheckConstraint(
            "deployment_mode IN ('experimental','shadow','approval_required',"
            "'limited_autonomy','active')",
            name="ck_onboarding_deployment_mode",
        ),
    )
    op.create_index(
        "ix_onboarding_sessions_business_status",
        "onboarding_sessions",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_onboarding_sessions_business_activity",
        "onboarding_sessions",
        ["business_id", "last_activity_at"],
    )

    op.create_table(
        "onboarding_responses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "onboarding_session_id",
            UUID,
            sa.ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(160), nullable=False),
        sa.Column("workflow_key", sa.String(160)),
        sa.Column("response_type", sa.String(40), nullable=False),
        sa.Column("response_value", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Numeric(7, 4)),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmed_by", sa.String(255)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("skip_explanation", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "onboarding_session_id",
            "question_key",
            name="uq_onboarding_response_question",
        ),
        sa.CheckConstraint(
            "source IN ('user','website_inferred','connector_inferred','imported','system')",
            name="ck_onboarding_response_source",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_onboarding_response_confidence",
        ),
    )
    op.create_index(
        "ix_onboarding_responses_business_session",
        "onboarding_responses",
        ["business_id", "onboarding_session_id"],
    )
    op.create_index(
        "ix_onboarding_responses_confirmation",
        "onboarding_responses",
        ["business_id", "requires_confirmation", "confirmed_at"],
    )

    for table_name in ("onboarding_sessions", "onboarding_responses"):
        op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE POLICY beoos_tenant_access ON {table_name} FOR ALL "
                "USING (beoos_can_access_business(business_id)) "
                "WITH CHECK (beoos_can_access_business(business_id))"
            )
        )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_onboarding_tenant()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE related_business_id uuid;
            BEGIN
                SELECT business_id INTO related_business_id
                FROM onboarding_sessions WHERE id = NEW.onboarding_session_id;
                IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                    RAISE EXCEPTION 'cross-tenant onboarding response';
                END IF;
                RETURN NEW;
            END;
            $$;
            CREATE TRIGGER trg_onboarding_responses_tenant_integrity
            BEFORE INSERT OR UPDATE ON onboarding_responses
            FOR EACH ROW EXECUTE FUNCTION beoos_assert_onboarding_tenant();
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_onboarding_responses_tenant_integrity "
            "ON onboarding_responses"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_onboarding_tenant()"))
    op.drop_table("onboarding_responses")
    op.drop_table("onboarding_sessions")
