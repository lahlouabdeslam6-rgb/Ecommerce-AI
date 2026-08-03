"""Add the pack cover selected in a marketing campaign.

Revision ID: 0011_marketing_pack_cover
Revises: 0010_packs
"""
import sqlalchemy as sa
from alembic import op


revision = "0011_marketing_pack_cover"
down_revision = "0010_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns("ai_marketing_campaigns")
    }
    if "pack_cover_image_url" not in columns:
        op.add_column(
            "ai_marketing_campaigns",
            sa.Column("pack_cover_image_url", sa.String(1000), nullable=True),
        )


def downgrade() -> None:
    connection = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns("ai_marketing_campaigns")
    }
    if "pack_cover_image_url" in columns:
        op.drop_column("ai_marketing_campaigns", "pack_cover_image_url")
