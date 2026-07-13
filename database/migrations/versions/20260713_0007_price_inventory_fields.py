"""Add flexible price catalogue inventory fields.

Revision ID: 20260713_0007
Revises: 20260712_0006
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260713_0007"
down_revision: str | Sequence[str] | None = "20260712_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("price_catalog_items", sa.Column("stock_quantity", sa.Integer()))
    op.add_column(
        "price_catalog_items",
        sa.Column(
            "custom_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column("price_catalog_items", "custom_fields", server_default=None)


def downgrade() -> None:
    op.drop_column("price_catalog_items", "custom_fields")
    op.drop_column("price_catalog_items", "stock_quantity")
