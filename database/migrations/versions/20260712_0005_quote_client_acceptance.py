"""Quote client acceptance and payment links.

Revision ID: 20260712_0005
Revises: 20260711_0004
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_0005"
down_revision: str | Sequence[str] | None = "20260711_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("public_token", sa.String(96)))
    op.execute(
        """
        UPDATE quotes
        SET public_token = encode(gen_random_bytes(32), 'hex')
        WHERE public_token IS NULL
        """
    )
    op.alter_column("quotes", "public_token", nullable=False)
    op.create_unique_constraint("uq_quotes_public_token", "quotes", ["public_token"])
    op.add_column("quotes", sa.Column("client_viewed_at", sa.DateTime(timezone=True)))
    op.add_column("quotes", sa.Column("payment_url", sa.Text()))
    op.add_column("quotes", sa.Column("payment_reference", sa.String(160)))


def downgrade() -> None:
    op.drop_column("quotes", "payment_reference")
    op.drop_column("quotes", "payment_url")
    op.drop_column("quotes", "client_viewed_at")
    op.drop_constraint("uq_quotes_public_token", "quotes", type_="unique")
    op.drop_column("quotes", "public_token")
