"""Add Creator Hub Phase 1: Revenue tracking and deal deliverables

Creates RevenueEntry for unified income tracking across all revenue streams.
Creates DealDeliverable for tracking sponsor deal deliverables with proof-of-performance.
Adds performance_report and report_generated_at fields to SalesPipeline.

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-01-17 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create revenue_entries table for unified income tracking
    op.create_table(
        'revenue_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('affiliate_revenue_id', sa.Integer(), nullable=True),
        sa.Column('pipeline_deal_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True, default='USD'),
        sa.Column('date_earned', sa.Date(), nullable=False),
        sa.Column('date_received', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('receipt_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_revenue_entry_user'),
        sa.ForeignKeyConstraint(['affiliate_revenue_id'], ['affiliate_revenue.id'], name='fk_revenue_entry_affiliate'),
        sa.ForeignKeyConstraint(['pipeline_deal_id'], ['sales_pipeline.id'], name='fk_revenue_entry_pipeline'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_revenue_entries_user_id', 'revenue_entries', ['user_id'], unique=False)
    op.create_index('ix_revenue_entries_source_type', 'revenue_entries', ['source_type'], unique=False)
    op.create_index('ix_revenue_entries_date_earned', 'revenue_entries', ['date_earned'], unique=False)
    op.create_index('ix_revenue_entries_affiliate_revenue_id', 'revenue_entries', ['affiliate_revenue_id'], unique=False)
    op.create_index('ix_revenue_entries_pipeline_deal_id', 'revenue_entries', ['pipeline_deal_id'], unique=False)

    # 2. Create deal_deliverables table for sponsor deliverable tracking
    op.create_table(
        'deal_deliverables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deal_id', sa.Integer(), nullable=False),
        sa.Column('deliverable_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('completed_date', sa.Date(), nullable=True),
        sa.Column('platform_post_url', sa.Text(), nullable=True),
        sa.Column('platform_post_id', sa.String(length=255), nullable=True),
        sa.Column('impressions', sa.Integer(), nullable=True),
        sa.Column('reach', sa.Integer(), nullable=True),
        sa.Column('engagement', sa.Integer(), nullable=True),
        sa.Column('clicks', sa.Integer(), nullable=True),
        sa.Column('conversions', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['deal_id'], ['sales_pipeline.id'], name='fk_deal_deliverable_deal'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deal_deliverables_deal_id', 'deal_deliverables', ['deal_id'], unique=False)
    op.create_index('ix_deal_deliverables_deliverable_type', 'deal_deliverables', ['deliverable_type'], unique=False)
    op.create_index('ix_deal_deliverables_due_date', 'deal_deliverables', ['due_date'], unique=False)
    op.create_index('ix_deal_deliverables_status', 'deal_deliverables', ['status'], unique=False)

    # 3. Add performance_report fields to sales_pipeline
    with op.batch_alter_table('sales_pipeline', schema=None) as batch_op:
        batch_op.add_column(sa.Column('performance_report', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('report_generated_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove performance_report fields from sales_pipeline
    with op.batch_alter_table('sales_pipeline', schema=None) as batch_op:
        batch_op.drop_column('report_generated_at')
        batch_op.drop_column('performance_report')

    # Drop deal_deliverables table
    op.drop_index('ix_deal_deliverables_status', table_name='deal_deliverables')
    op.drop_index('ix_deal_deliverables_due_date', table_name='deal_deliverables')
    op.drop_index('ix_deal_deliverables_deliverable_type', table_name='deal_deliverables')
    op.drop_index('ix_deal_deliverables_deal_id', table_name='deal_deliverables')
    op.drop_table('deal_deliverables')

    # Drop revenue_entries table
    op.drop_index('ix_revenue_entries_pipeline_deal_id', table_name='revenue_entries')
    op.drop_index('ix_revenue_entries_affiliate_revenue_id', table_name='revenue_entries')
    op.drop_index('ix_revenue_entries_date_earned', table_name='revenue_entries')
    op.drop_index('ix_revenue_entries_source_type', table_name='revenue_entries')
    op.drop_index('ix_revenue_entries_user_id', table_name='revenue_entries')
    op.drop_table('revenue_entries')
