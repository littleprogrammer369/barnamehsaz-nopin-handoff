"""Widen solver_assignments unique constraint to include resource_id.

Revision ID: 0010
Revises: 0009

Phase 4 stores dual-resource assignments (07 hard #8/#9): one
SolverAssignment row per resource (room + instructor) per occurrence,
so the original UNIQUE (run_id, offering_id, occurrence_no) constraint
from 0009 cannot hold. This incremental migration replaces it with
UNIQUE (run_id, offering_id, occurrence_no, resource_id).

It is idempotent: if the constraint already includes resource_id
(e.g. the test database was fixed by hand), the migration is a no-op.

"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_CONSTRAINT_NAME = "uq_solver_assignments_run_offering_occurrence"
_NEW_COLUMNS = ["run_id", "offering_id", "occurrence_no", "resource_id"]


def _constraint_columns() -> list:
    """Return the column names of the unique constraint, in order."""
    conn = op.get_bind()
    row = conn.execute(sa.text(
        """
        SELECT a.attname
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid
                                AND a.attnum = ANY (c.conkey)
        WHERE c.conname = :name
          AND a.attnum > 0
        ORDER BY a.attnum
        """
    ), {"name": _CONSTRAINT_NAME}).fetchall()
    return [r[0] for r in row]


def upgrade() -> None:
    cols = _constraint_columns()
    if cols == _NEW_COLUMNS:
        # Already widened (test DB was patched by hand) — nothing to do.
        return
    op.drop_constraint(_CONSTRAINT_NAME, "solver_assignments",
                       type_="unique")
    op.create_unique_constraint(
        _CONSTRAINT_NAME, "solver_assignments", _NEW_COLUMNS)


def downgrade() -> None:
    cols = _constraint_columns()
    if cols == ["run_id", "offering_id", "occurrence_no"]:
        # Already at the 0009 state.
        return
    op.drop_constraint(_CONSTRAINT_NAME, "solver_assignments",
                       type_="unique")
    op.create_unique_constraint(
        _CONSTRAINT_NAME, "solver_assignments",
        ["run_id", "offering_id", "occurrence_no"])
