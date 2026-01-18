"""Content models - episode guides and templates."""
from datetime import datetime, timezone
from extensions import db


class EpisodeGuideTemplate(db.Model):
    """Reusable template for episode guides with default sections and static content."""
    __tablename__ = 'episode_guide_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    # Podcast ownership
    podcast_id = db.Column(db.Integer, db.ForeignKey('podcasts.id'), nullable=True, index=True)

    # Default static content (JSON arrays of strings)
    intro_static_content = db.Column(db.JSON, nullable=True)  # ["line 1", "line 2", ...]
    outro_static_content = db.Column(db.JSON, nullable=True)  # ["line 1", "line 2", ...]

    # Default sections to include (JSON array of section definitions)
    # Format: [{"key": "news_mice", "name": "Mice", "parent": "news", "color": "red"}, ...]
    default_sections = db.Column(db.JSON, nullable=True)

    # Default poll questions
    default_poll_1 = db.Column(db.String(200), nullable=True)
    default_poll_2 = db.Column(db.String(200), nullable=True)

    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_default = db.Column(db.Boolean, default=False)  # Auto-select for new guides

    # Relationships
    creator = db.relationship('User', backref='episode_guide_templates')
    guides = db.relationship('EpisodeGuide', back_populates='template', lazy='dynamic')
    podcast = db.relationship('Podcast', back_populates='templates')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'podcast_id': self.podcast_id,
            'podcast_name': self.podcast.name if self.podcast else None,
            'intro_static_content': self.intro_static_content,
            'outro_static_content': self.outro_static_content,
            'default_sections': self.default_sections,
            'default_poll_1': self.default_poll_1,
            'default_poll_2': self.default_poll_2,
            'created_by': self.created_by,
            'creator_name': self.creator.name if self.creator else None,
            'is_default': self.is_default,
            'guide_count': self.guides.count() if self.guides else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class EpisodeGuide(db.Model):
    """Episode guide for live podcast recording with timestamp tracking."""
    __tablename__ = 'episode_guides'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    episode_number = db.Column(db.Integer, nullable=True, index=True)
    scheduled_date = db.Column(db.Date, nullable=True, index=True)  # Episode recording/publish date

    # Podcast ownership
    podcast_id = db.Column(db.Integer, db.ForeignKey('podcasts.id'), nullable=True, index=True)

    # Template reference (optional - guides can be created without template)
    template_id = db.Column(db.Integer, db.ForeignKey('episode_guide_templates.id'), nullable=True, index=True)

    # Recording state
    status = db.Column(db.String(20), default='draft', index=True)  # draft, recording, completed
    recording_started_at = db.Column(db.DateTime, nullable=True)
    recording_ended_at = db.Column(db.DateTime, nullable=True)
    total_duration_seconds = db.Column(db.Integer, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    # Poll fields for intro (title and link for each)
    previous_poll = db.Column(db.String(500), nullable=True)  # Title
    previous_poll_link = db.Column(db.String(500), nullable=True)
    new_poll = db.Column(db.String(500), nullable=True)  # Title
    new_poll_link = db.Column(db.String(500), nullable=True)

    # Static content for this guide (overrides template if set)
    intro_static_content = db.Column(db.JSON, nullable=True)  # ["line 1", "line 2", ...]
    outro_static_content = db.Column(db.JSON, nullable=True)  # ["line 1", "line 2", ...]

    # Custom sections added on-the-fly (supplements builtin + template sections)
    # Format: [{"key": "my_section", "name": "My Section", "parent": null, "color": "blue"}, ...]
    custom_sections = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    podcast = db.relationship('Podcast', back_populates='episodes')
    template = db.relationship('EpisodeGuideTemplate', back_populates='guides')
    items = db.relationship('EpisodeGuideItem', back_populates='guide', cascade='all, delete-orphan',
                           order_by='EpisodeGuideItem.section, EpisodeGuideItem.position', lazy='select')

    def get_intro_content(self):
        """Get intro static content (from guide, or fallback to template)."""
        if self.intro_static_content:
            return self.intro_static_content
        if self.template and self.template.intro_static_content:
            return self.template.intro_static_content
        return []

    def get_outro_content(self):
        """Get outro static content (from guide, or fallback to template)."""
        if self.outro_static_content:
            return self.outro_static_content
        if self.template and self.template.outro_static_content:
            return self.template.outro_static_content
        return []

    def get_all_sections(self):
        """Get all sections for this guide (builtin + template defaults + custom)."""
        from constants import EPISODE_GUIDE_SECTIONS, EPISODE_GUIDE_SECTION_NAMES, EPISODE_GUIDE_SECTION_PARENTS

        # Start with builtin sections
        sections = list(EPISODE_GUIDE_SECTIONS)

        # Add custom sections from this guide
        if self.custom_sections:
            for cs in self.custom_sections:
                if isinstance(cs, dict):
                    # Dict format: {"key": "...", "name": "...", "parent": "..."}
                    sections.append((cs['key'], cs['name'], cs.get('parent')))
                elif isinstance(cs, str):
                    # String format: just the key - look up name from builtins or use key
                    name = EPISODE_GUIDE_SECTION_NAMES.get(cs, cs.replace('_', ' ').title())
                    parent = EPISODE_GUIDE_SECTION_PARENTS.get(cs)
                    sections.append((cs, name, parent))

        return sections

    @property
    def formatted_duration(self):
        """Return formatted duration as HH:MM:SS or MM:SS."""
        if self.total_duration_seconds is None:
            return None
        hrs = self.total_duration_seconds // 3600
        mins = (self.total_duration_seconds % 3600) // 60
        secs = self.total_duration_seconds % 60
        if hrs > 0:
            return f"{hrs}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'episode_number': self.episode_number,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'podcast_id': self.podcast_id,
            'podcast_name': self.podcast.name if self.podcast else None,
            'template_id': self.template_id,
            'template_name': self.template.name if self.template else None,
            'status': self.status,
            'recording_started_at': self.recording_started_at.isoformat() if self.recording_started_at else None,
            'recording_ended_at': self.recording_ended_at.isoformat() if self.recording_ended_at else None,
            'total_duration_seconds': self.total_duration_seconds,
            'formatted_duration': self.formatted_duration,
            'notes': self.notes,
            'previous_poll': self.previous_poll,
            'previous_poll_link': self.previous_poll_link,
            'new_poll': self.new_poll,
            'new_poll_link': self.new_poll_link,
            'intro_static_content': self.get_intro_content(),
            'outro_static_content': self.get_outro_content(),
            'custom_sections': self.custom_sections,
            'item_count': len(self.items) if self.items else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class EpisodeGuideItem(db.Model):
    """Individual topic/item within an episode guide section."""
    __tablename__ = 'episode_guide_items'

    id = db.Column(db.Integer, primary_key=True)
    guide_id = db.Column(db.Integer, db.ForeignKey('episode_guides.id'), nullable=False, index=True)

    # Section identification (using predefined constants)
    section = db.Column(db.String(30), nullable=False, index=True)  # introduction, news_mice, etc.

    # Item content
    title = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500), nullable=True)  # Legacy single link (kept for migration)
    links = db.Column(db.JSON, nullable=True)  # Multiple links as ["url1", "url2"]
    notes = db.Column(db.Text, nullable=True)

    # Ordering within section
    position = db.Column(db.Integer, default=0, index=True)

    # Timestamp (captured during live recording - seconds from start)
    timestamp_seconds = db.Column(db.Integer, nullable=True)

    # Status tracking
    discussed = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    guide = db.relationship('EpisodeGuide', back_populates='items')

    @property
    def formatted_timestamp(self):
        """Return MM:SS or HH:MM:SS formatted timestamp."""
        if self.timestamp_seconds is None:
            return None
        hrs = self.timestamp_seconds // 3600
        mins = (self.timestamp_seconds % 3600) // 60
        secs = self.timestamp_seconds % 60
        if hrs > 0:
            return f"{hrs}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    @property
    def all_links(self):
        """Return list of all links (handles migration from single link)."""
        if self.links:
            return self.links
        if self.link:
            return [self.link]
        return []

    def to_dict(self):
        return {
            'id': self.id,
            'guide_id': self.guide_id,
            'section': self.section,
            'title': self.title,
            'link': self.link,
            'links': self.all_links,
            'notes': self.notes,
            'position': self.position,
            'timestamp_seconds': self.timestamp_seconds,
            'formatted_timestamp': self.formatted_timestamp,
            'discussed': self.discussed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
