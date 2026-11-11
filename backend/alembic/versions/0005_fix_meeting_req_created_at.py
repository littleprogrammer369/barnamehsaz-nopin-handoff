import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("meeting_requirements", "created_at", nullable=False)


def downgrade() -> None:
    op.alter_column("meeting_requirements", "created_at", nullable=True)
