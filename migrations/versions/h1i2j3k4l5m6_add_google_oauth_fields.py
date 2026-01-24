"""Add Google OAuth fields to User

Revision ID: h1i2j3k4l5m6
Revises: 565eb3b7c0f1
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h1i2j3k4l5m6'
down_revision = '565eb3b7c0f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('google_linked_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('auth_provider', sa.String(length=20), nullable=True))
        batch_op.create_index('ix_users_google_id', ['google_id'], unique=True)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_google_id')
        batch_op.drop_column('auth_provider')
        batch_op.drop_column('google_linked_at')
        batch_op.drop_column('google_id')
