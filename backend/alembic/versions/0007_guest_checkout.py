"""Allow secure guest checkout.

Revision ID: 0007_guest_checkout
Revises: 0006_automation_outbox
"""
import sqlalchemy as sa
from alembic import op


revision = "0007_guest_checkout"
down_revision = "0006_automation_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns("orders")
    }
    if {"email", "guest_token_hash"}.issubset(columns):
        return
    if "email" not in columns:
        op.add_column(
            "orders",
            sa.Column("email", sa.String(length=320), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE orders SET email = "
                "(SELECT users.email FROM users WHERE users.id = orders.user_id)"
            )
        )
    if "guest_token_hash" not in columns:
        op.add_column(
            "orders",
            sa.Column(
                "guest_token_hash",
                sa.String(length=64),
                nullable=True,
            ),
        )

    with op.batch_alter_table("orders", recreate="always") as batch:
        batch.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch.alter_column(
            "email",
            existing_type=sa.String(length=320),
            nullable=False,
        )
        batch.create_index("ix_orders_email", ["email"])
        batch.create_unique_constraint(
            "uq_orders_guest_token_hash",
            ["guest_token_hash"],
        )


def downgrade() -> None:
    with op.batch_alter_table("orders", recreate="always") as batch:
        batch.drop_constraint(
            "uq_orders_guest_token_hash",
            type_="unique",
        )
        batch.drop_index("ix_orders_email")
        batch.drop_column("guest_token_hash")
        batch.drop_column("email")
        batch.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
