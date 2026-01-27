"""Add server defaults to episode tweet config columns

Revision ID: 3bd4bac60dfe
Revises: 1b0d4c91ab09
Create Date: 2026-01-25 11:42:33.794445

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3bd4bac60dfe'
down_revision = '1b0d4c91ab09'
branch_labels = None
depends_on = None


def upgrade():
    # Add server_default values to ensure database-level defaults
    # This protects against NULL values from direct SQL inserts or data recovery

    # First set existing NULLs to default values
    op.execute("UPDATE episode_tweet_configs SET enabled = true WHERE enabled IS NULL")
    op.execute("UPDATE episode_tweet_configs SET include_url = true WHERE include_url IS NULL")
    op.execute("UPDATE episode_tweet_configs SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE episode_tweet_configs SET retry_count = 0 WHERE retry_count IS NULL")

    # Then add server defaults and make non-nullable
    with op.batch_alter_table('episode_tweet_configs', schema=None) as batch_op:
        batch_op.alter_column('enabled',
            existing_type=sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False)
        batch_op.alter_column('include_url',
            existing_type=sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False)
        batch_op.alter_column('status',
            existing_type=sa.String(length=20),
            server_default='pending',
            nullable=False)
        batch_op.alter_column('retry_count',
            existing_type=sa.Integer(),
            server_default='0',
            nullable=False)


def downgrade():
    with op.batch_alter_table('episode_tweet_configs', schema=None) as batch_op:
        batch_op.alter_column('enabled',
            existing_type=sa.Boolean(),
            server_default=None,
            nullable=True)
        batch_op.alter_column('include_url',
            existing_type=sa.Boolean(),
            server_default=None,
            nullable=True)
        batch_op.alter_column('status',
            existing_type=sa.String(length=20),
            server_default=None,
            nullable=True)
        batch_op.alter_column('retry_count',
            existing_type=sa.Integer(),
            server_default=None,
            nullable=True)
