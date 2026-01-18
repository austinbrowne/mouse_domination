"""Podcast models with role-based access control."""
from datetime import datetime, timezone
from extensions import db


class Podcast(db.Model):
    """A podcast that owns episodes and templates with role-based access control."""
    __tablename__ = 'podcasts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)  # URL-friendly identifier
    description = db.Column(db.Text, nullable=True)
    artwork_url = db.Column(db.String(500), nullable=True)  # Cover art
    website_url = db.Column(db.String(500), nullable=True)  # Podcast website
    rss_feed_url = db.Column(db.String(500), nullable=True)  # RSS feed

    # Creator (first admin, for reference)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Settings
    is_active = db.Column(db.Boolean, default=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_podcasts')
    members = db.relationship('PodcastMember', back_populates='podcast', cascade='all, delete-orphan')
    episodes = db.relationship('EpisodeGuide', back_populates='podcast', lazy='dynamic',
                               cascade='all, delete-orphan')
    templates = db.relationship('EpisodeGuideTemplate', back_populates='podcast', lazy='dynamic',
                                cascade='all, delete-orphan')

    def generate_slug(self):
        """Generate URL-friendly slug from name."""
        import re
        slug = self.name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug

    def get_admins(self):
        """Get all admin members of this podcast."""
        return [m for m in self.members if m.role == 'admin']

    def get_contributors(self):
        """Get all contributor members of this podcast."""
        return [m for m in self.members if m.role == 'contributor']

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'artwork_url': self.artwork_url,
            'website_url': self.website_url,
            'rss_feed_url': self.rss_feed_url,
            'created_by': self.created_by,
            'is_active': self.is_active,
            'episode_count': self.episodes.count() if self.episodes else 0,
            'template_count': self.templates.count() if self.templates else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PodcastMember(db.Model):
    """Users who have access to a podcast with role-based permissions.

    Roles:
    - 'admin': Can edit podcast settings, add/remove members, full episode/template access
    - 'contributor': Can create/edit episodes and templates, but not manage podcast settings
    """
    __tablename__ = 'podcast_members'

    id = db.Column(db.Integer, primary_key=True)
    podcast_id = db.Column(db.Integer, db.ForeignKey('podcasts.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default='contributor')  # 'admin' or 'contributor'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    podcast = db.relationship('Podcast', back_populates='members')
    user = db.relationship('User', foreign_keys=[user_id], backref='podcast_memberships')
    adder = db.relationship('User', foreign_keys=[added_by])

    __table_args__ = (
        db.UniqueConstraint('podcast_id', 'user_id', name='unique_podcast_member'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'podcast_id': self.podcast_id,
            'user_id': self.user_id,
            'user_email': self.user.email if self.user else None,
            'user_name': self.user.name if self.user else None,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'added_by': self.added_by,
        }
