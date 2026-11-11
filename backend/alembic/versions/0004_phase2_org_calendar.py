"""Phase 2: Organization / Planning Cycle / Resources / Calendar.

Tables added:
  planning_cycles, units, cycle_units,
  resources, resource_availability, resource_commitments,
  cohorts, cycle_cohorts, courses, course_offerings,
  offering_units, offering_cohorts, meeting_requirements

Design notes (05 / 06):
- Canonical organization-wide resources; per-cycle availability windows.
- No auto-merge of resource identities (explicit admin op, pending Q5).
- Normalized join tables for offerings <-> units / cohorts.
- Single MeetingRequirement per offering (shared-offering rule).
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------- planning_cycles ----------------
    op.create_table(
        "planning_cycles",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("term", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_planning_cycles_org_name"),
        sa.Index("ix_planning_cycles_organization_id", "organization_id"),
    )

    # ---------------- units ----------------
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_units_org_name"),
        sa.Index("ix_units_organization_id", "organization_id"),
    )

    # ---------------- cycle_units ----------------
    op.create_table(
        "cycle_units",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("responsible_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cycle_id", "unit_id", name="uq_cycle_units"),
        sa.Index("ix_cycle_units_cycle_id", "cycle_id"),
        sa.Index("ix_cycle_units_unit_id", "unit_id"),
    )

    # ---------------- resources ----------------
    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "kind", "name", name="uq_resources_org_kind_name"),
        sa.CheckConstraint(
            "kind <> 'room' OR capacity IS NULL OR capacity > 0",
            name="ck_resources_room_capacity_positive",
        ),
        sa.Index("ix_resources_organization_id", "organization_id"),
    )

    # ---------------- resource_availability ----------------
    op.create_table(
        "resource_availability",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_hhmm", sa.String(5), nullable=False),
        sa.Column("end_hhmm", sa.String(5), nullable=False),
        sa.UniqueConstraint("resource_id", "cycle_id", "weekday", "start_hhmm", "end_hhmm",
                            name="uq_resource_availability"),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_availability_weekday"),
        sa.Index("ix_resource_availability_resource_id", "resource_id"),
        sa.Index("ix_resource_availability_cycle_id", "cycle_id"),
    )

    # ---------------- resource_commitments ----------------
    op.create_table(
        "resource_commitments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_hhmm", sa.String(5), nullable=False),
        sa.Column("end_hhmm", sa.String(5), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_commitment_weekday"),
        sa.Index("ix_resource_commitments_resource_id", "resource_id"),
        sa.Index("ix_resource_commitments_cycle_id", "cycle_id"),
    )

    # ---------------- cohorts ----------------
    op.create_table(
        "cohorts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entry_year", sa.Integer(), nullable=True),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("unit_id", "name", name="uq_cohorts_unit_name"),
        sa.Index("ix_cohorts_unit_id", "unit_id"),
        sa.Index("ix_cohorts_organization_id", "organization_id"),
    )

    # ---------------- cycle_cohorts ----------------
    op.create_table(
        "cycle_cohorts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cohort_id", sa.Integer(), sa.ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expected_enrollment", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("cycle_id", "cohort_id", name="uq_cycle_cohorts"),
        sa.CheckConstraint("expected_enrollment >= 0", name="ck_cycle_cohorts_enrollment_nonneg"),
        sa.Index("ix_cycle_cohorts_cycle_id", "cycle_id"),
        sa.Index("ix_cycle_cohorts_cohort_id", "cohort_id"),
    )

    # ---------------- courses ----------------
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_courses_org_code"),
        sa.Index("ix_courses_organization_id", "organization_id"),
    )

    # ---------------- course_offerings ----------------
    op.create_table(
        "course_offerings",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("planning_cycle_id", sa.Integer(),
                  sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(64), nullable=True),
        sa.Column("meetings_per_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("required_room_capacity", sa.Integer(), nullable=True),
        sa.Column("room_type", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("planning_cycle_id", "course_id", "section",
                            name="uq_offerings_cycle_course_section"),
        sa.CheckConstraint("meetings_per_week > 0", name="ck_offerings_meetings_positive"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_offerings_duration_positive"),
        sa.Index("ix_offerings_course_id", "course_id"),
        sa.Index("ix_offerings_planning_cycle_id", "planning_cycle_id"),
    )

    # ---------------- offering_units ----------------
    op.create_table(
        "offering_units",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("offering_id", sa.Integer(),
                  sa.ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expected_enrollment", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("offering_id", "unit_id", name="uq_offering_units"),
        sa.CheckConstraint("expected_enrollment >= 0", name="ck_offering_units_enrollment_nonneg"),
        sa.Index("ix_offering_units_offering_id", "offering_id"),
        sa.Index("ix_offering_units_unit_id", "unit_id"),
    )

    # ---------------- offering_cohorts ----------------
    op.create_table(
        "offering_cohorts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("offering_id", sa.Integer(),
                  sa.ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cohort_id", sa.Integer(), sa.ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expected_enrollment", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("offering_id", "cohort_id", name="uq_offering_cohorts"),
        sa.CheckConstraint("expected_enrollment >= 0", name="ck_offering_cohorts_enrollment_nonneg"),
        sa.Index("ix_offering_cohorts_offering_id", "offering_id"),
        sa.Index("ix_offering_cohorts_cohort_id", "cohort_id"),
    )

    # ---------------- meeting_requirements ----------------
    op.create_table(
        "meeting_requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("offering_id", sa.Integer(),
                  sa.ForeignKey("course_offerings.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("allowed_weekday_min", sa.Integer(), nullable=True),
        sa.Column("allowed_weekday_max", sa.Integer(), nullable=True),
        sa.Column("start_window_hhmm", sa.String(5), nullable=True),
        sa.Column("end_window_hhmm", sa.String(5), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "allowed_weekday_min IS NULL OR allowed_weekday_max IS NULL "
            "OR allowed_weekday_min <= allowed_weekday_max",
            name="ck_meeting_req_weekday_range",
        ),
        sa.Index("ix_meeting_requirements_offering_id", "offering_id"),
    )


def downgrade() -> None:
    op.drop_table("meeting_requirements")
    op.drop_table("offering_cohorts")
    op.drop_table("offering_units")
    op.drop_table("course_offerings")
    op.drop_table("courses")
    op.drop_table("cycle_cohorts")
    op.drop_table("cohorts")
    op.drop_table("resource_commitments")
    op.drop_table("resource_availability")
    op.drop_table("resources")
    op.drop_table("cycle_units")
    op.drop_table("units")
    op.drop_table("planning_cycles")

