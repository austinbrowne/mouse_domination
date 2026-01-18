"""Add Content Atomizer Phase 2: AI content generation tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-01-17

Creates tables for:
- content_atomic_templates: AI prompt templates for each platform
- content_atomic_snippets: Generated content snippets
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    # Create content_atomic_templates table
    op.create_table('content_atomic_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('tone', sa.String(length=50), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('include_hashtags', sa.Boolean(), default=False),
        sa.Column('include_emoji', sa.Boolean(), default=False),
        sa.Column('include_cta', sa.Boolean(), default=False),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('times_used', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_content_atomic_templates_user_id', 'content_atomic_templates', ['user_id'], unique=False)
    op.create_index('idx_content_atomic_templates_platform', 'content_atomic_templates', ['platform'], unique=False)

    # Create content_atomic_snippets table
    op.create_table('content_atomic_snippets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False, default='manual'),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_title', sa.String(length=255), nullable=True),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('source_content', sa.Text(), nullable=False),
        sa.Column('generated_content', sa.Text(), nullable=False),
        sa.Column('edited_content', sa.Text(), nullable=True),
        sa.Column('character_count', sa.Integer(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('hashtags', sa.JSON(), nullable=True),
        sa.Column('ai_model', sa.String(length=50), nullable=True),
        sa.Column('ai_temperature', sa.Float(), nullable=True),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), default='draft'),
        sa.Column('scheduled_date', sa.DateTime(), nullable=True),
        sa.Column('published_date', sa.DateTime(), nullable=True),
        sa.Column('published_url', sa.Text(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('feedback_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['content_atomic_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_content_atomic_snippets_user_id', 'content_atomic_snippets', ['user_id'], unique=False)
    op.create_index('idx_content_atomic_snippets_platform', 'content_atomic_snippets', ['platform'], unique=False)
    op.create_index('idx_content_atomic_snippets_status', 'content_atomic_snippets', ['status'], unique=False)
    op.create_index('idx_content_atomic_snippets_source_type', 'content_atomic_snippets', ['source_type'], unique=False)
    op.create_index('idx_content_atomic_snippets_created_at', 'content_atomic_snippets', ['created_at'], unique=False)
    op.create_index('idx_content_atomic_snippets_source_id', 'content_atomic_snippets', ['source_id'], unique=False)


def downgrade():
    op.drop_index('idx_content_atomic_snippets_source_id', table_name='content_atomic_snippets')
    op.drop_index('idx_content_atomic_snippets_created_at', table_name='content_atomic_snippets')
    op.drop_index('idx_content_atomic_snippets_source_type', table_name='content_atomic_snippets')
    op.drop_index('idx_content_atomic_snippets_status', table_name='content_atomic_snippets')
    op.drop_index('idx_content_atomic_snippets_platform', table_name='content_atomic_snippets')
    op.drop_index('idx_content_atomic_snippets_user_id', table_name='content_atomic_snippets')
    op.drop_table('content_atomic_snippets')

    op.drop_index('idx_content_atomic_templates_platform', table_name='content_atomic_templates')
    op.drop_index('idx_content_atomic_templates_user_id', table_name='content_atomic_templates')
    op.drop_table('content_atomic_templates')
