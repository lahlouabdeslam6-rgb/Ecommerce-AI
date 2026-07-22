"""Add safe soft deletion for user accounts.

Revision ID: 0002_soft_delete_users
Revises: 0001_baseline
"""
import sqlalchemy as sa
from alembic import op


revision = "0002_soft_delete_users"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in sa.inspect(connection).get_columns("users")}
    if "is_deleted" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.create_index("ix_users_is_deleted", "users", ["is_deleted"])


def downgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in sa.inspect(connection).get_columns("users")}
    if "is_deleted" in columns:
        op.drop_index("ix_users_is_deleted", table_name="users")
        op.drop_column("users", "is_deleted")
