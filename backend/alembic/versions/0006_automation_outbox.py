"""Add automation outbox.

Revision ID: 0006_automation_outbox
Revises: 0005_ai_safety
"""
import sqlalchemy as sa
from alembic import op


revision = "0006_automation_outbox"
down_revision = "0005_ai_safety"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if "automation_outbox" in sa.inspect(connection).get_table_names():
        return
    op.create_table(
        "automation_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=180), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in (
        "event_type",
        "channel",
        "reference_type",
        "reference_id",
        "status",
        "created_at",
    ):
        op.create_index(
            f"ix_automation_outbox_{column}",
            "automation_outbox",
            [column],
        )


def downgrade() -> None:
    connection = op.get_bind()
    if "automation_outbox" in sa.inspect(connection).get_table_names():
        op.drop_table("automation_outbox")

