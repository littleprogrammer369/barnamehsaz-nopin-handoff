"""Add unit_id to memberships table for unit_manager role binding.

Revision ID: 0014
Revises: 0013

Unit managers are responsible for exactly one unit. This migration adds an
optional FK that is NOT NULL for unit_manager role and NULL for admin role.
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add unit_id column (nullable initially)
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.add_column(
            sa.Column("unit_id", sa.Integer(), nullable=True)
        )
    
    # Step 2: Backfill unit_managers from CycleUnit.responsible_user_id
    # For each unit_manager, find their responsible unit(s) from CycleUnit
    # Use the most recent cycle to determine unit assignment
    connection = op.get_bind()
    
    # Find all unit_managers and assign them to a unit
    backfill_sql = """
    UPDATE memberships m
    SET unit_id = (
        SELECT DISTINCT cu.unit_id
        FROM cycle_units cu
        WHERE cu.responsible_user_id = m.user_id
        ORDER BY cu.created_at DESC
        LIMIT 1
    )
    WHERE m.role = 'unit_manager'
    AND m.unit_id IS NULL
    AND EXISTS (
        SELECT 1 FROM cycle_units cu 
        WHERE cu.responsible_user_id = m.user_id
    )
    """
    connection.execute(sa.text(backfill_sql))
    
    # Step 3: Add foreign key constraint
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.create_foreign_key(
            "fk_memberships_unit_id",
            "units",
            ["unit_id"],
            ["id"],
        )
    
    # Step 4: Add index
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.create_index(
            "ix_memberships_unit_id",
            ["unit_id"],
        )
    
    # Step 5: Add check constraint (after backfill, so existing data is safe)
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.create_check_constraint(
            "ck_memberships_unit_role_consistency",
            "(role = 'unit_manager' AND unit_id IS NOT NULL) OR (role != 'unit_manager' AND unit_id IS NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_constraint("ck_memberships_unit_role_consistency", type_="check")
        batch_op.drop_index("ix_memberships_unit_id")
        batch_op.drop_constraint("fk_memberships_unit_id", type_="foreignkey")
        batch_op.drop_column("unit_id")
