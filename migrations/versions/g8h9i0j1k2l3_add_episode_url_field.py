"""Add episode_url field to episode_guides

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g8h9i0j1k2l3'
down_revision = 'f7g8h9i0j1k2'
branch_labels = None
depends_on = None


def upgrade():
    # Add episode_url column to episode_guides table
    op.add_column('episode_guides', sa.Column('episode_url', sa.String(500), nullable=True))


def downgrade():
    # Remove episode_url column from episode_guides table
    op.drop_column('episode_guides', 'episode_url')
