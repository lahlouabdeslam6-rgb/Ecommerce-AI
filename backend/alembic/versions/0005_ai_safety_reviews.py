"""Add Safety Agent review history.

Revision ID: 0005_ai_safety
Revises: 0004_ai_marketing
"""
import sqlalchemy as sa
from alembic import op


revision = "0005_ai_safety"
down_revision = "0004_ai_marketing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if "ai_safety_reviews" in sa.inspect(connection).get_table_names():
        return
    op.create_table(
        "ai_safety_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("recommendations_json", sa.Text(), nullable=False),
        sa.Column("matched_rules_json", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "source_type",
        "source_id",
        "action",
        "status",
        "risk_level",
        "actor_id",
        "created_at",
    ):
        op.create_index(
            f"ix_ai_safety_reviews_{column}",
            "ai_safety_reviews",
            [column],
        )


def downgrade() -> None:
    connection = op.get_bind()
    if "ai_safety_reviews" in sa.inspect(connection).get_table_names():
        op.drop_table("ai_safety_reviews")
