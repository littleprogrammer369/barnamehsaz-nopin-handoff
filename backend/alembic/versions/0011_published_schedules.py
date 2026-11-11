"""Add published_schedules table.

Revision ID: 0011
Revises: 0010

Creates the published_schedules envelope table for immutable,
versioned published schedules (08).
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"


def upgrade() -> None:
    op.create_table(
        "published_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("run_id", sa.Integer(),
                  sa.ForeignKey("solver_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("cycle_id", sa.Integer(),
                  sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False,
                  server_default="draft"),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("result_snapshot", sa.JSON(), nullable=True),
        sa.Column("source_run_id", sa.Integer(),
                  sa.ForeignKey("solver_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stale_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  index=sa.Index("ix_published_schedules_created_at", "created_at")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','current','previous','stale')",
            name="ck_published_schedules_status",
        ),
    )
    op.create_index("ix_published_schedules_run_id", "published_schedules", ["run_id"])
    op.create_index("ix_published_schedules_cycle_id", "published_schedules", ["cycle_id"])
    op.create_index("ix_published_schedules_org_id", "published_schedules", ["organization_id"])
    op.create_index(
        "ix_published_schedules_status_lookup",
        "published_schedules",
        ["organization_id", "status", "cycle_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_published_schedules_status_lookup", table_name="published_schedules")
    op.drop_index("ix_published_schedules_org_id", table_name="published_schedules")
    op.drop_index("ix_published_schedules_cycle_id", table_name="published_schedules")
    op.drop_index("ix_published_schedules_run_id", table_name="published_schedules")
    op.drop_table("published_schedules")
