"""Add YouTube live title filter to podcasts

Revision ID: i2j3k4l5m6n7
Revises: 3bd4bac60dfe
Create Date: 2026-01-25

Adds:
- youtube_title_filter to podcasts table (optional text to match in live stream title)
- youtube_title_filter_enabled to podcasts table (toggle for filtering)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i2j3k4l5m6n7'
down_revision = '3bd4bac60dfe'
branch_labels = None
depends_on = None


def upgrade():
    # Add youtube_title_filter columns to podcasts table
    op.add_column('podcasts', sa.Column('youtube_title_filter', sa.String(200), nullable=True))
    op.add_column('podcasts', sa.Column('youtube_title_filter_enabled', sa.Boolean(),
                                        nullable=False, server_default='false'))


def downgrade():
    op.drop_column('podcasts', 'youtube_title_filter_enabled')
    op.drop_column('podcasts', 'youtube_title_filter')
