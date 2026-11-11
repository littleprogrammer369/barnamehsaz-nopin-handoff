"""Add organization_id to security audit_events so security events can be
scoped to the caller's org (consistent with Phase 2/3 org-scoped model)."""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("organization_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_column("audit_events", "organization_id")
