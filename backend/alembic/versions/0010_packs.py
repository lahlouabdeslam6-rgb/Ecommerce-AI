"""Add independent packs, pack cart items and pack order metadata.

Revision ID: 0010_packs
Revises: 0009_promotion_signals
"""
import sqlalchemy as sa
from alembic import op


revision = "0010_packs"
down_revision = "0009_promotion_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())
    if "packs" not in tables:
        op.create_table(
            "packs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(180), nullable=False),
            sa.Column("slug", sa.String(220), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("highlights_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("main_image_url", sa.String(1000), nullable=True),
            sa.Column("gallery_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("regular_price", sa.Float(), nullable=False),
            sa.Column("discount_percentage", sa.Float(), nullable=False, server_default="0"),
            sa.Column("promotional_price", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="MAD"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("source", sa.String(20), nullable=False, server_default="admin"),
            sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("ai_marketing_campaigns.id", ondelete="SET NULL"), nullable=True, unique=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "pack_items" not in tables:
        op.create_table(
            "pack_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pack_id", sa.Integer(), sa.ForeignKey("packs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("pack_id", "product_id"),
        )
    if "pack_cart_items" not in tables:
        op.create_table(
            "pack_cart_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("pack_id", sa.Integer(), sa.ForeignKey("packs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "pack_id"),
        )
    columns = {column["name"] for column in sa.inspect(connection).get_columns("order_items")}
    if "pack_id" not in columns:
        with op.batch_alter_table("order_items") as batch:
            batch.add_column(sa.Column("pack_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_order_items_pack_id", "packs", ["pack_id"], ["id"], ondelete="RESTRICT")
    if "item_type" not in columns:
        op.add_column("order_items", sa.Column("item_type", sa.String(20), nullable=False, server_default="product"))


def downgrade() -> None:
    with op.batch_alter_table("order_items") as batch:
        batch.drop_column("item_type")
        batch.drop_column("pack_id")
    op.drop_table("pack_cart_items")
    op.drop_table("pack_items")
    op.drop_table("packs")
