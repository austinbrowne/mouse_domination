"""Add performance indexes for query optimization

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-16 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Inventory compound index for filtered list queries (most critical)
    # Covers: user_id + status + category filtering
    op.create_index(
        'ix_inventory_user_status_category',
        'inventory',
        ['user_id', 'status', 'category']
    )

    # Pipeline status + deadline index for deadline queries
    op.create_index(
        'ix_sales_pipeline_status_deadline',
        'sales_pipeline',
        ['status', 'deadline']
    )

    # Collaboration follow-up index for follow-up queries
    op.create_index(
        'ix_collaboration_follow_up',
        'collaborations',
        ['follow_up_needed', 'follow_up_date']
    )

    # Affiliate revenue compound index for user+year queries
    op.create_index(
        'ix_affiliate_revenue_user_year_month',
        'affiliate_revenue',
        ['user_id', 'year', 'month']
    )


def downgrade():
    op.drop_index('ix_affiliate_revenue_user_year_month', table_name='affiliate_revenue')
    op.drop_index('ix_collaboration_follow_up', table_name='collaborations')
    op.drop_index('ix_sales_pipeline_status_deadline', table_name='sales_pipeline')
    op.drop_index('ix_inventory_user_status_category', table_name='inventory')
