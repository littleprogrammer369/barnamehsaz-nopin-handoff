"""Add deleted_at soft-delete columns to planning_cycles and resource_availability tables.

Revision ID: 0013
Revises: 0012
Allow additive soft-delete: rows can be logically removed without cascade physical deletion,
respecting audit requirements that referenced rows must not be hard-deleted.
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # planning_cycles: add nullable deleted_at timestamp
    with op.batch_alter_table("planning_cycles") as batch_op:
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(), nullable=True)
        )

    # resource_availability: add nullable deleted_at timestamp
    with op.batch_alter_table("resource_availability") as batch_op:
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    # resource_availability: remove column
    with op.batch_alter_table("resource_availability") as batch_op:
        batch_op.drop_column("deleted_at")

    # planning_cycles: remove column (guard against NULLs if any)
    op.execute(sa.text("UPDATE planning_cycles SET deleted_at = NULL WHERE deleted_at IS NOT NULL"))
    with op.batch_alter_table("planning_cycles") as batch_op:
        batch_op.drop_column("deleted_at")