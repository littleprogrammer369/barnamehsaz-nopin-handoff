"""Add submission_comments table (Phase 3 comment/annotation).

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.create_table(
        "submission_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(),
                  sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_submission_comments_submission_id",
                   "submission_comments", ["submission_id"])
    op.create_index("ix_submission_comments_restriction",
                   "submission_comments", ["submission_id", "revision_no"])


def downgrade() -> None:
    op.drop_index("ix_submission_comments_restriction",
                  table_name="submission_comments")
    op.drop_index("ix_submission_comments_submission_id",
                  table_name="submission_comments")
    op.drop_table("submission_comments")
