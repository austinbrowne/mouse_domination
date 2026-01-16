"""Add index to inventory created_at

Revision ID: f744066e33f4
Revises:
Create Date: 2026-01-16 12:28:02.694069

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f744066e33f4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_inventory_created_at', 'inventory', ['created_at'], unique=False, if_not_exists=True)


def downgrade():
    op.drop_index('ix_inventory_created_at', table_name='inventory')
