"""Make planning_cycles.term nullable.

Revision ID: 0012
Revises: 0011
Allow term to be null so UI can omit an optional label without triggering validation errors.
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Allow NULL values in the existing column (drop NOT NULL constraint)
    with op.batch_alter_table("planning_cycles") as batch_op:
        batch_op.alter_column("term", existing_type=sa.String(128), nullable=True)


def downgrade() -> None:
    # Re-apply NOT NULL constraint - any rows that have NULL will fail,
    # so we guard by setting term to empty string where NULL exists first.
    op.execute(sa.text("UPDATE planning_cycles SET term = '' WHERE term IS NULL"))
    with op.batch_alter_table("planning_cycles") as batch_op:
        batch_op.alter_column("term", existing_type=sa.String(128), nullable=False)
