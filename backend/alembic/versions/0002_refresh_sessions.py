"""Add refresh_sessions table for server-side refresh token storage.

Security closeout (Phase 1 / Q4):
- refresh tokens are stored only as a SHA-256 hash (``token_hash``), never raw
- ``family_id`` groups rotations of a single login session
- rotation / replay / logout / password change all revoke rows on the server
"""

from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None


def upgrade():
    op.create_table(
        'refresh_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('family_id', sa.String(36), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_refresh_sessions_token_hash', 'refresh_sessions', ['token_hash'], unique=True)
    op.create_index('ix_refresh_sessions_user_id', 'refresh_sessions', ['user_id'])
    op.create_index('ix_refresh_sessions_family_id', 'refresh_sessions', ['family_id'])


def downgrade():
    op.drop_index('ix_refresh_sessions_family_id', table_name='refresh_sessions')
    op.drop_index('ix_refresh_sessions_user_id', table_name='refresh_sessions')
    op.drop_index('ix_refresh_sessions_token_hash', table_name='refresh_sessions')
    op.drop_table('refresh_sessions')
