"""initial schema

Revision ID: 20260308_0001
Revises:
Create Date: 2026-03-08 00:00:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260308_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("payment_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("paid_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("payment_id"),
    )

    op.create_table(
        "credits",
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_table(
        "queue_items",
        sa.Column("queue_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("song_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("queue_id"),
    )

    op.create_table(
        "processed_webhook_events",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("payment_id", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("processed_webhook_events")
    op.drop_table("queue_items")
    op.drop_table("credits")
    op.drop_table("payments")

