"""Add Marketing Agent campaign workflow.

Revision ID: 0004_ai_marketing
Revises: 0003_ai_contents
"""
import sqlalchemy as sa
from alembic import op


revision = "0004_ai_marketing"
down_revision = "0003_ai_contents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if "ai_marketing_campaigns" in sa.inspect(connection).get_table_names():
        return
    op.create_table(
        "ai_marketing_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_type", sa.String(length=40), nullable=False),
        sa.Column("topic", sa.String(length=300), nullable=False),
        sa.Column("objective", sa.String(length=500), nullable=False),
        sa.Column("audience", sa.String(length=160), nullable=False),
        sa.Column("tone", sa.String(length=30), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("offer_details", sa.String(length=500), nullable=True),
        sa.Column("channels_json", sa.Text(), nullable=False),
        sa.Column("campaign_title", sa.String(length=180), nullable=False),
        sa.Column("headline", sa.String(length=220), nullable=False),
        sa.Column("core_message", sa.Text(), nullable=False),
        sa.Column("email_subject", sa.String(length=180), nullable=True),
        sa.Column("email_body", sa.Text(), nullable=True),
        sa.Column("whatsapp_message", sa.Text(), nullable=True),
        sa.Column("social_caption", sa.Text(), nullable=True),
        sa.Column("cta_label", sa.String(length=80), nullable=False),
        sa.Column("hashtags_json", sa.Text(), nullable=False),
        sa.Column(
            "recommended_schedule",
            sa.String(length=300),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "campaign_type",
        "product_id",
        "status",
        "created_by",
        "approved_at",
        "created_at",
    ):
        op.create_index(
            f"ix_ai_marketing_campaigns_{column}",
            "ai_marketing_campaigns",
            [column],
        )


def downgrade() -> None:
    connection = op.get_bind()
    if "ai_marketing_campaigns" in sa.inspect(connection).get_table_names():
        op.drop_table("ai_marketing_campaigns")
