"""Create the initial DocuSense schema.

Revision ID: 20260908_0001
Revises:
"""
from alembic import op
from sqlmodel import SQLModel

from app.models import document  # noqa: F401

revision = "20260908_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The SQLModel metadata is the single schema source for this baseline migration.
    SQLModel.metadata.create_all(op.get_bind())


def downgrade() -> None:
    SQLModel.metadata.drop_all(op.get_bind())
