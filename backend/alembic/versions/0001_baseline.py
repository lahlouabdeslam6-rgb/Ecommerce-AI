"""Create the complete NUTRIFIT SQLite schema.

Revision ID: 0001_baseline
Revises:
"""
from alembic import op

from app.db.sqlite import Base
from app.models import *  # noqa: F403


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
