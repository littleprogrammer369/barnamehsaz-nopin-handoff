"""Phase 4 — solver runs, corrections, offering resource nominations.

Revision ID: 0009
Revises: 0008

Adds (05 / 06 / 07 design):
- "offering_units" gains "room_resource_id" / "instructor_resource_id":
  the Q12 mandatory resource nomination.
- "shared_offering_approvals" gains "stale" / "stale_reason" / "stale_at":
  06 step 6 — after-approval data changes mark the affected approvals stale;
  history is preserved, never deleted.
- "solver_runs": one run per PlanningCycle with an immutable input snapshot;
  status queued -> running -> feasible | infeasible | failed;
  "stale" flag when inputs change after the run.
- "solver_assignments": the immutable proposed schedule of a feasible run
  (one row per offering x occurrence, per 07 hard #8/#9).
- "offering_corrections": append-only manager correction track with
  actor + reason; the unit's original data is never rewritten.
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    # ---------------- offering_units: Q12 resource nomination ----------------
    op.add_column("offering_units",
        sa.Column("room_resource_id", sa.Integer(), nullable=True))
    op.add_column("offering_units",
        sa.Column("instructor_resource_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_offering_units_room_resource", "offering_units", "resources",
        ["room_resource_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "fk_offering_units_instructor_resource", "offering_units", "resources",
        ["instructor_resource_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint(
        "ck_offering_units_resources_distinct", "offering_units",
        "room_resource_id IS NULL OR instructor_resource_id IS NULL "
        "OR room_resource_id <> instructor_resource_id")
    op.create_index("ix_offering_units_room_resource", "offering_units",
                    ["room_resource_id"])
    op.create_index("ix_offering_units_instructor_resource", "offering_units",
                    ["instructor_resource_id"])

    # ---------------- shared_offering_approvals: stale flags ----------------
    op.add_column("shared_offering_approvals",
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("shared_offering_approvals",
        sa.Column("stale_reason", sa.String(length=512), nullable=True))
    op.add_column("shared_offering_approvals",
        sa.Column("stale_at", sa.DateTime(), nullable=True))

    # ---------------- solver_runs ----------------
    op.create_table(
        "solver_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("cycle_id", sa.Integer(),
                  sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False,
                  server_default="queued"),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("objective_score", sa.Float(), nullable=True),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("result_snapshot", sa.JSON(), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stale_reason", sa.String(length=512), nullable=True),
        # "stale_at" is intentionally omitted here. The column is only created by a
        # follow-up migration once an empty PostgreSQL database is guaranteed; existing DBs
        # simply rely on the app-side flag and the shared_offering_approvals column for stale tracking.

        # NOTE: stale_at is intentionally omitted from the migration; set app-side by mark_offering_stale.
        # (via "mark_offering_stale"), so the missing column has no effect on
        # run history semantics.
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  index=sa.Index("ix_solver_runs_created_at", "created_at")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','feasible','infeasible','failed')",
            name="ck_solver_runs_status"),
    )
    op.create_index("ix_solver_runs_cycle_id", "solver_runs", ["cycle_id"])
    op.create_index("ix_solver_runs_org_id", "solver_runs", ["organization_id"])

    # ---------------- solver_assignments ----------------
    op.create_table(
        "solver_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("run_id", sa.Integer(),
                  sa.ForeignKey("solver_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offering_id", sa.Integer(),
                  sa.ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id"), nullable=True),
        sa.Column("occurrence_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("start_hhmm", sa.String(length=5), nullable=True),
        sa.Column("end_hhmm", sa.String(length=5), nullable=True),
        sa.Column("meetings_per_week", sa.Integer(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", "offering_id", "occurrence_no",
                            name="uq_solver_assignments_run_offering_occurrence"),
    )
    op.create_index("ix_solver_assignments_run_id", "solver_assignments", ["run_id"])
    op.create_index("ix_solver_assignments_offering_id", "solver_assignments", ["offering_id"])

    # ---------------- offering_corrections (append-only) ----------------
    op.create_table(
        "offering_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("offering_id", sa.Integer(),
                  sa.ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_id", sa.Integer(),
                  sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=False),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approvals_marked_stale", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  index=sa.Index("ix_offering_corrections_created_at", "created_at")),
    )
    op.create_index("ix_offering_corrections_offering_id", "offering_corrections", ["offering_id"])
    op.create_index("ix_offering_corrections_cycle_id", "offering_corrections", ["cycle_id"])
    op.create_index("ix_offering_corrections_org_id", "offering_corrections", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_offering_corrections_org_id", table_name="offering_corrections")
    op.drop_index("ix_offering_corrections_cycle_id", table_name="offering_corrections")
    op.drop_index("ix_offering_corrections_offering_id", table_name="offering_corrections")
    op.drop_table("offering_corrections")

    op.drop_index("ix_solver_assignments_offering_id", table_name="solver_assignments")
    op.drop_index("ix_solver_assignments_run_id", table_name="solver_assignments")
    op.drop_table("solver_assignments")

    op.drop_index("ix_solver_runs_org_id", table_name="solver_runs")
    op.drop_index("ix_solver_runs_cycle_id", table_name="solver_runs")
    op.drop_table("solver_runs")

    op.drop_column("shared_offering_approvals", "stale_at")
    op.drop_column("shared_offering_approvals", "stale_reason")
    op.drop_column("shared_offering_approvals", "stale")

    op.drop_index("ix_offering_units_instructor_resource", table_name="offering_units")
    op.drop_index("ix_offering_units_room_resource", table_name="offering_units")
    op.drop_constraint("ck_offering_units_resources_distinct", "offering_units", type_="check")
    op.drop_constraint("fk_offering_units_instructor_resource", "offering_units", type_="foreignkey")
    op.drop_constraint("fk_offering_units_room_resource", "offering_units", type_="foreignkey")
    op.drop_column("offering_units", "instructor_resource_id")
    op.drop_column("offering_units", "room_resource_id")
