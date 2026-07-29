"""Harden MCP access and complete marketing evidence records.

Revision ID: 20260729_0028
Revises: 20260727_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0028"
down_revision: str | None = "20260727_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "marketing_opportunities",
        sa.Column("property", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "marketing_opportunities",
        sa.Column("evidence_period_start", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "marketing_opportunities",
        sa.Column("evidence_period_end", sa.DateTime(timezone=True)),
    )
    op.execute(
        sa.text(
            "UPDATE marketing_opportunities "
            "SET evidence_period_start = created_at - INTERVAL '90 days', "
            "evidence_period_end = created_at"
        )
    )
    op.alter_column("marketing_opportunities", "evidence_period_start", nullable=False)
    op.alter_column("marketing_opportunities", "evidence_period_end", nullable=False)
    op.add_column(
        "marketing_opportunities",
        sa.Column("detected_issue", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "marketing_opportunities",
        sa.Column("limitations", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "marketing_experiments",
        sa.Column("interpretation", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "marketing_experiments",
        sa.Column("confounding_factors", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("marketing_experiments", sa.Column("approved_by", sa.String(255)))
    op.add_column(
        "marketing_experiments",
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )
    op.drop_constraint(
        "ck_marketing_experiment_status",
        "marketing_experiments",
        type_="check",
    )
    op.create_check_constraint(
        "ck_marketing_experiment_status",
        "marketing_experiments",
        "status IN "
        "('draft','pending_approval','approved','measurement_pending','completed','cancelled')",
    )

    op.create_table(
        "external_api_request_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "token_id",
            UUID,
            sa.ForeignKey("external_api_tokens.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(160), nullable=False),
        sa.Column("method", sa.String(120), nullable=False),
        sa.Column("tool_name", sa.String(160), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message_safe", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_external_api_requests_token_created",
        "external_api_request_logs",
        ["token_id", "created_at"],
    )
    op.create_index(
        "ix_external_api_requests_business_created",
        "external_api_request_logs",
        ["business_id", "created_at"],
    )
    op.create_index(
        "ix_external_api_requests_correlation",
        "external_api_request_logs",
        ["correlation_id"],
    )
    op.execute(sa.text("ALTER TABLE external_api_request_logs ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY beoos_tenant_access ON external_api_request_logs FOR ALL "
            "USING (beoos_can_access_business(business_id)) "
            "WITH CHECK (beoos_can_access_business(business_id))"
        )
    )


def downgrade() -> None:
    op.drop_table("external_api_request_logs")
    op.drop_constraint(
        "ck_marketing_experiment_status",
        "marketing_experiments",
        type_="check",
    )
    op.create_check_constraint(
        "ck_marketing_experiment_status",
        "marketing_experiments",
        "status IN ('approved','measurement_pending','completed','cancelled')",
    )
    op.drop_column("marketing_experiments", "approved_at")
    op.drop_column("marketing_experiments", "approved_by")
    op.drop_column("marketing_experiments", "confounding_factors")
    op.drop_column("marketing_experiments", "interpretation")
    op.drop_column("marketing_opportunities", "limitations")
    op.drop_column("marketing_opportunities", "detected_issue")
    op.drop_column("marketing_opportunities", "evidence_period_end")
    op.drop_column("marketing_opportunities", "evidence_period_start")
    op.drop_column("marketing_opportunities", "property")
