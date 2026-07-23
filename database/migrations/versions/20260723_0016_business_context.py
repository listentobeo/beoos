"""Add versioned tenant business context.

Revision ID: 20260723_0016
Revises: 20260723_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0016"
down_revision: str | None = "20260723_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
ROLE = postgresql.ENUM("owner", "admin", "agent", "viewer", name="role", create_type=False)
TABLES = (
    "business_profiles",
    "business_services",
    "business_policies",
    "business_staff_authorities",
)


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def _provenance() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("authority_level", sa.String(40), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("approval_status", sa.String(40), nullable=False),
        sa.Column("approved_by", sa.String(255)),
    )


def upgrade() -> None:
    op.create_table(
        "business_profiles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("legal_name", sa.String(240), nullable=False, server_default=""),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("industry", sa.String(160), nullable=False, server_default=""),
        sa.Column("business_model", sa.String(160), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("locations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("opening_hours", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("contact_channels", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("website", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_markets", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("customer_types", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_provenance(),
        sa.Column("supersedes_id", UUID, sa.ForeignKey("business_profiles.id")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("business_id", "version", name="uq_business_profile_version"),
    )
    op.create_index(
        "ix_business_profiles_business_active", "business_profiles", ["business_id", "active"]
    )

    op.create_table(
        "business_services",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("service_key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("base_pricing_reference", sa.String(255)),
        sa.Column(
            "required_enquiry_information",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("typical_timeline", sa.String(255), nullable=False, server_default=""),
        sa.Column("delivery_method", sa.String(255), nullable=False, server_default=""),
        sa.Column("exclusions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_provenance(),
        sa.Column("supersedes_id", UUID, sa.ForeignKey("business_services.id")),
        *_timestamps(),
        sa.UniqueConstraint(
            "business_id", "service_key", "version", name="uq_business_service_version"
        ),
    )
    op.create_index(
        "ix_business_services_business_active", "business_services", ["business_id", "active"]
    )

    op.create_table(
        "business_policies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("policy_key", sa.String(120), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rules", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_provenance(),
        sa.Column("supersedes_id", UUID, sa.ForeignKey("business_policies.id")),
        *_timestamps(),
        sa.UniqueConstraint(
            "business_id", "policy_key", "version", name="uq_business_policy_version"
        ),
        sa.CheckConstraint(
            "category IN ('communication','pricing','discounts','refunds','commitments',"
            "'delivery','privacy','escalation','prohibited_claims','legal_sensitive',"
            "'marketing','channel_specific')",
            name="ck_business_policy_category",
        ),
    )
    op.create_index(
        "ix_business_policies_business_active", "business_policies", ["business_id", "active"]
    )
    op.create_index(
        "ix_business_policies_business_category",
        "business_policies",
        ["business_id", "category"],
    )

    op.create_table(
        "business_staff_authorities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("clerk_user_id", sa.String(255), nullable=False),
        sa.Column("role", ROLE, nullable=False),
        sa.Column(
            "approval_authority", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("financial_limit", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("channel_access", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("escalation_responsibility", sa.Text(), nullable=False, server_default=""),
        *_provenance(),
        *_timestamps(),
        sa.UniqueConstraint(
            "business_id", "clerk_user_id", name="uq_business_staff_authority_user"
        ),
    )
    op.create_index(
        "ix_business_staff_authorities_business",
        "business_staff_authorities",
        ["business_id"],
    )

    for table_name in TABLES:
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
            CREATE OR REPLACE FUNCTION beoos_assert_context_tenant()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE related_business_id uuid;
            BEGIN
                IF TG_TABLE_NAME = 'business_profiles' AND NEW.supersedes_id IS NOT NULL THEN
                    SELECT business_id INTO related_business_id
                    FROM business_profiles WHERE id = NEW.supersedes_id;
                ELSIF TG_TABLE_NAME = 'business_services' AND NEW.supersedes_id IS NOT NULL THEN
                    SELECT business_id INTO related_business_id
                    FROM business_services WHERE id = NEW.supersedes_id;
                ELSIF TG_TABLE_NAME = 'business_policies' AND NEW.supersedes_id IS NOT NULL THEN
                    SELECT business_id INTO related_business_id
                    FROM business_policies WHERE id = NEW.supersedes_id;
                ELSE
                    RETURN NEW;
                END IF;
                IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                    RAISE EXCEPTION 'cross-tenant context version';
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    for table_name in ("business_profiles", "business_services", "business_policies"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table_name}_tenant_integrity "
                f"BEFORE INSERT OR UPDATE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION beoos_assert_context_tenant()"
            )
        )


def downgrade() -> None:
    for table_name in ("business_profiles", "business_services", "business_policies"):
        op.execute(
            sa.text(f"DROP TRIGGER IF EXISTS trg_{table_name}_tenant_integrity ON {table_name}")
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_context_tenant()"))
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
