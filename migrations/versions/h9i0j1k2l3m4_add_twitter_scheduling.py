"""Add Twitter scheduling for podcast episodes

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-01-24

Adds:
- youtube_channel_id to podcasts table (for live stream detection)
- episode_tweet_configs table (per-host tweet configuration per episode)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h9i0j1k2l3m4'
down_revision = 'g8h9i0j1k2l3'
branch_labels = None
depends_on = None


def upgrade():
    # Add youtube_channel_id to podcasts table
    op.add_column('podcasts', sa.Column('youtube_channel_id', sa.String(100), nullable=True))

    # Create episode_tweet_configs table
    op.create_table('episode_tweet_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('episode_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('generated_content', sa.Text(), nullable=True),
        sa.Column('custom_content', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('include_url', sa.Boolean(), default=True),
        sa.Column('status', sa.String(length=20), default='pending'),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
        sa.Column('tweet_id', sa.String(length=100), nullable=True),
        sa.Column('tweet_url', sa.String(length=500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['episode_id'], ['episode_guides.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('episode_id', 'user_id', name='unique_episode_tweet_per_user')
    )
    op.create_index('idx_episode_tweet_configs_episode_id', 'episode_tweet_configs', ['episode_id'], unique=False)
    op.create_index('idx_episode_tweet_configs_user_id', 'episode_tweet_configs', ['user_id'], unique=False)
    op.create_index('idx_episode_tweet_configs_status', 'episode_tweet_configs', ['status'], unique=False)


def downgrade():
    op.drop_index('idx_episode_tweet_configs_status', table_name='episode_tweet_configs')
    op.drop_index('idx_episode_tweet_configs_user_id', table_name='episode_tweet_configs')
    op.drop_index('idx_episode_tweet_configs_episode_id', table_name='episode_tweet_configs')
    op.drop_table('episode_tweet_configs')

    op.drop_column('podcasts', 'youtube_channel_id')
