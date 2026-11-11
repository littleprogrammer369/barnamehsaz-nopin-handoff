"""Phase 3: submissions, revisions, wizard drafts, shared-offering approvals,
and a domain audit trail.

Tables added:
  submissions, submission_revisions, wizard_drafts,
  shared_offering_approvals, domain_audit_events

Design notes (05 / 06 / 08):
- Submission is the active row per (cycle, unit); status transitions are
  server-enforced and locked once submitted.
- SubmissionRevision is append-only (new rows, no mutation).
- SharedOfferingApproval: one explicit approval per (offering, unit); a shared
  offering cannot be solved/published without all + manager finalization.
- DomainAuditEvent is an append-only trail distinct from security audit_events.
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------- submissions ----------------
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cycle_id", "unit_id", name="uq_submissions_cycle_unit"),
        sa.CheckConstraint(
            "status IN ('draft','submitted','needs_changes','approved')",
            name="ck_submissions_status",
        ),
    )
    op.create_index("ix_submissions_cycle_id", "submissions", ["cycle_id"], unique=False)
    op.create_index("ix_submissions_unit_id", "submissions", ["unit_id"], unique=False)
    op.create_index("ix_submissions_organization_id", "submissions", ["organization_id"], unique=False)

    # ---------------- submission_revisions (append-only) ----------------
    op.create_table(
        "submission_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("submission_id", "revision_no", name="uq_submission_revisions_no"),
    )
    op.create_index("ix_submission_revisions_submission_id", "submission_revisions", ["submission_id"], unique=False)
    op.create_index("ix_submission_revisions_created_by", "submission_revisions", ["created_by_user_id"], unique=False)

    # ---------------- wizard_drafts ----------------
    op.create_table(
        "wizard_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cycle_id", "unit_id", name="uq_wizard_drafts_cycle_unit"),
    )
    op.create_index("ix_wizard_drafts_cycle_id", "wizard_drafts", ["cycle_id"], unique=False)
    op.create_index("ix_wizard_drafts_unit_id", "wizard_drafts", ["unit_id"], unique=False)

    # ---------------- shared_offering_approvals ----------------
    op.create_table(
        "shared_offering_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("offering_id", sa.Integer(), sa.ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("offering_id", "unit_id", name="uq_shared_approvals_offering_unit"),
        sa.CheckConstraint(
            "status IN ('pending','unit_approved','needs_changes')",
            name="ck_shared_approvals_status",
        ),
    )
    op.create_index("ix_shared_approvals_offering_id", "shared_offering_approvals", ["offering_id"], unique=False)
    op.create_index("ix_shared_approvals_unit_id", "shared_offering_approvals", ["unit_id"], unique=False)

    # ---------------- domain_audit_events (append-only) ----------------
    op.create_table(
        "domain_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("subject_type", sa.String(64), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_domain_audit_events_action", "domain_audit_events", ["action"], unique=False)
    op.create_index("ix_domain_audit_events_org_id", "domain_audit_events", ["organization_id"], unique=False)
    op.create_index("ix_domain_audit_events_created_at", "domain_audit_events", ["created_at"], unique=False)
    op.create_index("ix_domain_audit_events_subject", "domain_audit_events", ["subject_type", "subject_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_domain_audit_events_subject", table_name="domain_audit_events")
    op.drop_index("ix_domain_audit_events_created_at", table_name="domain_audit_events")
    op.drop_index("ix_domain_audit_events_org_id", table_name="domain_audit_events")
    op.drop_index("ix_domain_audit_events_action", table_name="domain_audit_events")
    op.drop_table("domain_audit_events")

    op.drop_index("ix_shared_approvals_unit_id", table_name="shared_offering_approvals")
    op.drop_index("ix_shared_approvals_offering_id", table_name="shared_offering_approvals")
    op.drop_table("shared_offering_approvals")

    op.drop_index("ix_wizard_drafts_unit_id", table_name="wizard_drafts")
    op.drop_index("ix_wizard_drafts_cycle_id", table_name="wizard_drafts")
    op.drop_table("wizard_drafts")

    op.drop_index("ix_submission_revisions_created_by", table_name="submission_revisions")
    op.drop_index("ix_submission_revisions_submission_id", table_name="submission_revisions")
    op.drop_table("submission_revisions")

    op.drop_index("ix_submissions_organization_id", table_name="submissions")
    op.drop_index("ix_submissions_unit_id", table_name="submissions")
    op.drop_index("ix_submissions_cycle_id", table_name="submissions")
    op.drop_table("submissions")
