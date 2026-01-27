"""Merge Google OAuth and Twitter scheduling migrations

Revision ID: 1b0d4c91ab09
Revises: h1i2j3k4l5m6, h9i0j1k2l3m4
Create Date: 2026-01-24 15:30:27.776597

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b0d4c91ab09'
down_revision = ('h1i2j3k4l5m6', 'h9i0j1k2l3m4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
