"""Add unique constraints to prevent duplicate revenue sync entries

Revision ID: f6g7h8i9j0k1
Revises: a1b2c3d4e5f6
Create Date: 2026-01-19 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6g7h8i9j0k1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add unique constraint on user_id + affiliate_revenue_id (partial - where not null)
    # This prevents duplicate revenue entries when syncing affiliate revenue
    op.create_index(
        'ix_revenue_entries_unique_affiliate',
        'revenue_entries',
        ['user_id', 'affiliate_revenue_id'],
        unique=True,
        postgresql_where=sa.text('affiliate_revenue_id IS NOT NULL')
    )

    # Add unique constraint on user_id + pipeline_deal_id (partial - where not null)
    # This prevents duplicate revenue entries when syncing sponsorship deals
    op.create_index(
        'ix_revenue_entries_unique_pipeline',
        'revenue_entries',
        ['user_id', 'pipeline_deal_id'],
        unique=True,
        postgresql_where=sa.text('pipeline_deal_id IS NOT NULL')
    )


def downgrade():
    op.drop_index('ix_revenue_entries_unique_pipeline', table_name='revenue_entries')
    op.drop_index('ix_revenue_entries_unique_affiliate', table_name='revenue_entries')
