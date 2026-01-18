"""Add Social Posting Phase 3: OAuth connections and post logging

Revision ID: f7g8h9i0j1k2
Revises: e5f6g7h8i9j0
Create Date: 2026-01-17

Creates tables for:
- social_connections: OAuth connections to Twitter/X
- social_post_logs: Audit log of posts made via the app
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7g8h9i0j1k2'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade():
    # Create social_connections table
    op.create_table('social_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('platform_user_id', sa.String(length=100), nullable=True),
        sa.Column('platform_username', sa.String(length=100), nullable=True),
        sa.Column('encrypted_credentials', sa.Text(), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'platform', name='unique_user_platform')
    )
    op.create_index('idx_social_connections_user_id', 'social_connections', ['user_id'], unique=False)
    op.create_index('idx_social_connections_platform', 'social_connections', ['platform'], unique=False)

    # Create social_post_logs table
    op.create_table('social_post_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('snippet_id', sa.Integer(), nullable=True),
        sa.Column('connection_id', sa.Integer(), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('content_posted', sa.Text(), nullable=False),
        sa.Column('success', sa.Boolean(), default=False),
        sa.Column('platform_post_id', sa.String(length=100), nullable=True),
        sa.Column('platform_post_url', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['snippet_id'], ['content_atomic_snippets.id'], ),
        sa.ForeignKeyConstraint(['connection_id'], ['social_connections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_social_post_logs_user_id', 'social_post_logs', ['user_id'], unique=False)
    op.create_index('idx_social_post_logs_snippet_id', 'social_post_logs', ['snippet_id'], unique=False)
    op.create_index('idx_social_post_logs_platform', 'social_post_logs', ['platform'], unique=False)
    op.create_index('idx_social_post_logs_posted_at', 'social_post_logs', ['posted_at'], unique=False)


def downgrade():
    op.drop_index('idx_social_post_logs_posted_at', table_name='social_post_logs')
    op.drop_index('idx_social_post_logs_platform', table_name='social_post_logs')
    op.drop_index('idx_social_post_logs_snippet_id', table_name='social_post_logs')
    op.drop_index('idx_social_post_logs_user_id', table_name='social_post_logs')
    op.drop_table('social_post_logs')

    op.drop_index('idx_social_connections_platform', table_name='social_connections')
    op.drop_index('idx_social_connections_user_id', table_name='social_connections')
    op.drop_table('social_connections')
