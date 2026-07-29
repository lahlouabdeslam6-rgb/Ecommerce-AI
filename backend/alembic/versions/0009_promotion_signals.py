"""Add private product costs and anonymous product views.

Revision ID: 0009_promotion_signals
Revises: 0008_marketing_promotions
"""
import sqlalchemy as sa
from alembic import op


revision = "0009_promotion_signals"
down_revision = "0008_marketing_promotions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())
    if "product_costs" not in tables:
        op.create_table(
            "product_costs",
            sa.Column("product_id", sa.Integer(), primary_key=True),
            sa.Column("cost_price", sa.Float(), nullable=False),
            sa.Column(
                "currency",
                sa.String(length=3),
                nullable=False,
                server_default="MAD",
            ),
            sa.Column(
                "updated_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_product_costs_updated_by",
            "product_costs",
            ["updated_by"],
        )
    if "product_views" not in tables:
        op.create_table(
            "product_views",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column(
                "viewed_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_product_views_product_id",
            "product_views",
            ["product_id"],
        )
        op.create_index(
            "ix_product_views_viewed_at",
            "product_views",
            ["viewed_at"],
        )


def downgrade() -> None:
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())
    if "product_views" in tables:
        op.drop_table("product_views")
    if "product_costs" in tables:
        op.drop_table("product_costs")
