"""Platform MFA and single-use step-up authorization; additive only."""
from alembic import op
import sqlalchemy as sa
revision = 'f6a1b2o7'
down_revision = 'f6a1b2o6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('platform_mfa',
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('system_platform_accounts.id'), primary_key=True),
        sa.Column('secret', sa.Text(), nullable=False), sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_counter', sa.Integer(), nullable=False), sa.Column('recovery_hashes', sa.JSON(), nullable=False),
        sa.Column('failures', sa.Integer(), nullable=False), sa.Column('blocked_until', sa.DateTime(timezone=True)))
    op.create_table('platform_step_up',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('system_platform_accounts.id'), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False), sa.Column('binding', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False), sa.Column('used', sa.Boolean(), nullable=False))
    op.create_index('ix_platform_step_up_account_id', 'platform_step_up', ['account_id'])


def downgrade():
    # Preserve enrolled factors during rollback; never silently erase recovery credentials.
    raise RuntimeError('Security data is retained: roll back application code without dropping MFA tables')
