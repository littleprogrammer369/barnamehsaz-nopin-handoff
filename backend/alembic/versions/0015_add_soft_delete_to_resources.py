"""Add soft-delete (deleted_at) to resources table.

Revision ID: 0015
Revises: 0014

Allows resources to be logically deleted without cascade hard-delete of
referenced offering/commitment rows, preserving audit history.
"""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("resources") as batch_op:
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_column("deleted_at")
