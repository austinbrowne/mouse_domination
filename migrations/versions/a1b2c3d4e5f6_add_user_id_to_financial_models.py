"""Add user_id to financial models for multi-user data isolation

Revision ID: a1b2c3d4e5f6
Revises: e7ff28363667
Create Date: 2026-01-16 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e7ff28363667'
branch_labels = None
depends_on = None


def upgrade():
    # Add user_id column to affiliate_revenue (nullable first for existing data)
    with op.batch_alter_table('affiliate_revenue', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_affiliate_revenue_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_affiliate_revenue_user_id',
            'users',
            ['user_id'],
            ['id']
        )
        # Drop old constraint and add new one that includes user_id
        batch_op.drop_constraint('unique_company_month', type_='unique')
        batch_op.create_unique_constraint(
            'unique_user_company_month',
            ['user_id', 'company_id', 'year', 'month']
        )

    # Add user_id column to collaborations (nullable first for existing data)
    with op.batch_alter_table('collaborations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_collaborations_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_collaborations_user_id',
            'users',
            ['user_id'],
            ['id']
        )

    # Add user_id column to sales_pipeline (nullable first for existing data)
    with op.batch_alter_table('sales_pipeline', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_sales_pipeline_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_sales_pipeline_user_id',
            'users',
            ['user_id'],
            ['id']
        )

    # Migrate existing data: assign all existing records to the first admin user
    # This is a data migration - find admin user and assign ownership
    connection = op.get_bind()

    # Find the first admin user (or first approved user as fallback)
    admin_user = connection.execute(
        sa.text("SELECT id FROM users WHERE is_admin = true ORDER BY id LIMIT 1")
    ).fetchone()

    if admin_user:
        admin_id = admin_user[0]
    else:
        # Fallback to first approved user
        any_user = connection.execute(
            sa.text("SELECT id FROM users WHERE is_approved = true ORDER BY id LIMIT 1")
        ).fetchone()
        admin_id = any_user[0] if any_user else None

    if admin_id:
        # Update all existing records to belong to admin user
        connection.execute(
            sa.text(f"UPDATE affiliate_revenue SET user_id = {admin_id} WHERE user_id IS NULL")
        )
        connection.execute(
            sa.text(f"UPDATE collaborations SET user_id = {admin_id} WHERE user_id IS NULL")
        )
        connection.execute(
            sa.text(f"UPDATE sales_pipeline SET user_id = {admin_id} WHERE user_id IS NULL")
        )


def downgrade():
    with op.batch_alter_table('sales_pipeline', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sales_pipeline_user_id', type_='foreignkey')
        batch_op.drop_index('ix_sales_pipeline_user_id')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('collaborations', schema=None) as batch_op:
        batch_op.drop_constraint('fk_collaborations_user_id', type_='foreignkey')
        batch_op.drop_index('ix_collaborations_user_id')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('affiliate_revenue', schema=None) as batch_op:
        # Restore old constraint before dropping column
        batch_op.drop_constraint('unique_user_company_month', type_='unique')
        batch_op.create_unique_constraint(
            'unique_company_month',
            ['company_id', 'year', 'month']
        )
        batch_op.drop_constraint('fk_affiliate_revenue_user_id', type_='foreignkey')
        batch_op.drop_index('ix_affiliate_revenue_user_id')
        batch_op.drop_column('user_id')
