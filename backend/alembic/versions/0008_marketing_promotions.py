"""Add scored product and pack promotions.

Revision ID: 0008_marketing_promotions
Revises: 0007_guest_checkout
"""
import sqlalchemy as sa
from alembic import op


revision = "0008_marketing_promotions"
down_revision = "0007_guest_checkout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns(
            "ai_marketing_campaigns"
        )
    }
    additions = {
        "promotion_kind": sa.Column(
            "promotion_kind", sa.String(length=30), nullable=True
        ),
        "selection_mode": sa.Column(
            "selection_mode", sa.String(length=30), nullable=True
        ),
        "product_ids_json": sa.Column(
            "product_ids_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        "selection_scores_json": sa.Column(
            "selection_scores_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        "discount_percentage": sa.Column(
            "discount_percentage", sa.Float(), nullable=True
        ),
        "starts_at": sa.Column(
            "starts_at", sa.DateTime(timezone=True), nullable=True
        ),
        "ends_at": sa.Column(
            "ends_at", sa.DateTime(timezone=True), nullable=True
        ),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("ai_marketing_campaigns", column)
    indexes = {
        index["name"]
        for index in sa.inspect(connection).get_indexes(
            "ai_marketing_campaigns"
        )
    }
    for name in ("promotion_kind", "starts_at", "ends_at"):
        index_name = f"ix_ai_marketing_campaigns_{name}"
        if index_name not in indexes:
            op.create_index(
                index_name,
                "ai_marketing_campaigns",
                [name],
            )


def downgrade() -> None:
    connection = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns(
            "ai_marketing_campaigns"
        )
    }
    indexes = {
        index["name"]
        for index in sa.inspect(connection).get_indexes(
            "ai_marketing_campaigns"
        )
    }
    for name in ("promotion_kind", "starts_at", "ends_at"):
        index_name = f"ix_ai_marketing_campaigns_{name}"
        if index_name in indexes:
            op.drop_index(index_name, table_name="ai_marketing_campaigns")
    for name in (
        "ends_at",
        "starts_at",
        "discount_percentage",
        "selection_scores_json",
        "product_ids_json",
        "selection_mode",
        "promotion_kind",
    ):
        if name in columns:
            op.drop_column("ai_marketing_campaigns", name)
