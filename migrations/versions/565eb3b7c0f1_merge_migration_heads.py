"""Merge migration heads

Revision ID: 565eb3b7c0f1
Revises: f6g7h8i9j0k1, g8h9i0j1k2l3
Create Date: 2026-01-23 19:03:02.233780

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '565eb3b7c0f1'
down_revision = ('f6g7h8i9j0k1', 'g8h9i0j1k2l3')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
