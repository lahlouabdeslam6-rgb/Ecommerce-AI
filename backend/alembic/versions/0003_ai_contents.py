"""Add Content Agent drafts and publishing workflow.

Revision ID: 0003_ai_contents
Revises: 0002_soft_delete_users
"""
import sqlalchemy as sa
from alembic import op


revision = "0003_ai_contents"
down_revision = "0002_soft_delete_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if "ai_contents" in sa.inspect(connection).get_table_names():
        return
    op.create_table(
        "ai_contents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("topic", sa.String(length=300), nullable=False),
        sa.Column("objective", sa.String(length=500), nullable=True),
        sa.Column("audience", sa.String(length=120), nullable=False),
        sa.Column("tone", sa.String(length=30), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("cta_label", sa.String(length=80), nullable=True),
        sa.Column("hashtags_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "content_type",
        "product_id",
        "status",
        "created_by",
        "published_at",
        "created_at",
    ):
        op.create_index(
            f"ix_ai_contents_{column}",
            "ai_contents",
            [column],
        )


def downgrade() -> None:
    connection = op.get_bind()
    if "ai_contents" in sa.inspect(connection).get_table_names():
        op.drop_table("ai_contents")
