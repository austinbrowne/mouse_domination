"""Add podcast ownership and access control

Creates Podcast and PodcastMember models for multi-user podcast ownership.
Migrates existing episodes and templates to a default 'MouseCast' podcast.

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-16 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create podcasts table
    op.create_table(
        'podcasts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('artwork_url', sa.String(length=500), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('rss_feed_url', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_podcast_created_by'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_podcasts_slug', 'podcasts', ['slug'], unique=True)
    op.create_index('ix_podcasts_created_by', 'podcasts', ['created_by'], unique=False)

    # 2. Create podcast_members table
    op.create_table(
        'podcast_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('podcast_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, default='contributor'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['podcast_id'], ['podcasts.id'], name='fk_podcast_member_podcast'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_podcast_member_user'),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'], name='fk_podcast_member_added_by'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('podcast_id', 'user_id', name='unique_podcast_member')
    )
    op.create_index('ix_podcast_members_podcast_id', 'podcast_members', ['podcast_id'], unique=False)
    op.create_index('ix_podcast_members_user_id', 'podcast_members', ['user_id'], unique=False)

    # 3. Add podcast_id to episode_guides
    with op.batch_alter_table('episode_guides', schema=None) as batch_op:
        batch_op.add_column(sa.Column('podcast_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_episode_guides_podcast_id', ['podcast_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_episode_guide_podcast',
            'podcasts',
            ['podcast_id'],
            ['id']
        )

    # 4. Add podcast_id to episode_guide_templates
    with op.batch_alter_table('episode_guide_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('podcast_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_episode_guide_templates_podcast_id', ['podcast_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_episode_guide_template_podcast',
            'podcasts',
            ['podcast_id'],
            ['id']
        )

    # 5. Data migration: Create MouseCast podcast and migrate existing data
    connection = op.get_bind()

    # Find the first admin user (creator of MouseCast)
    admin_user = connection.execute(
        sa.text("SELECT id FROM users WHERE is_admin = true ORDER BY id LIMIT 1")
    ).fetchone()

    if admin_user:
        creator_id = admin_user[0]
    else:
        # Fallback to first approved user
        any_user = connection.execute(
            sa.text("SELECT id FROM users WHERE is_approved = true ORDER BY id LIMIT 1")
        ).fetchone()
        creator_id = any_user[0] if any_user else None

    if creator_id:
        # Create MouseCast podcast
        connection.execute(
            sa.text("""
                INSERT INTO podcasts (name, slug, description, created_by, is_active, created_at, updated_at)
                VALUES ('MouseCast', 'mousecast', 'The MouseCast podcast', :creator_id, true, NOW(), NOW())
            """),
            {'creator_id': creator_id}
        )

        # Get the MouseCast podcast ID
        result = connection.execute(
            sa.text("SELECT id FROM podcasts WHERE slug = 'mousecast'")
        ).fetchone()
        mousecast_id = result[0] if result else None

        if mousecast_id:
            # Add ALL approved users as admins of MouseCast
            connection.execute(
                sa.text("""
                    INSERT INTO podcast_members (podcast_id, user_id, role, created_at, added_by)
                    SELECT :podcast_id, id, 'admin', NOW(), :added_by
                    FROM users
                    WHERE is_approved = true
                """),
                {'podcast_id': mousecast_id, 'added_by': creator_id}
            )

            # Migrate existing episodes to MouseCast
            connection.execute(
                sa.text("UPDATE episode_guides SET podcast_id = :podcast_id WHERE podcast_id IS NULL"),
                {'podcast_id': mousecast_id}
            )

            # Migrate existing templates to MouseCast
            connection.execute(
                sa.text("UPDATE episode_guide_templates SET podcast_id = :podcast_id WHERE podcast_id IS NULL"),
                {'podcast_id': mousecast_id}
            )


def downgrade():
    # Remove podcast_id from episode_guide_templates
    with op.batch_alter_table('episode_guide_templates', schema=None) as batch_op:
        batch_op.drop_constraint('fk_episode_guide_template_podcast', type_='foreignkey')
        batch_op.drop_index('ix_episode_guide_templates_podcast_id')
        batch_op.drop_column('podcast_id')

    # Remove podcast_id from episode_guides
    with op.batch_alter_table('episode_guides', schema=None) as batch_op:
        batch_op.drop_constraint('fk_episode_guide_podcast', type_='foreignkey')
        batch_op.drop_index('ix_episode_guides_podcast_id')
        batch_op.drop_column('podcast_id')

    # Drop podcast_members table
    op.drop_index('ix_podcast_members_user_id', table_name='podcast_members')
    op.drop_index('ix_podcast_members_podcast_id', table_name='podcast_members')
    op.drop_table('podcast_members')

    # Drop podcasts table
    op.drop_index('ix_podcasts_created_by', table_name='podcasts')
    op.drop_index('ix_podcasts_slug', table_name='podcasts')
    op.drop_table('podcasts')
