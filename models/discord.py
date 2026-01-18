"""Discord integration models for community topic sourcing."""
from datetime import datetime, timezone
from extensions import db


class DiscordIntegration(db.Model):
    """Discord channel configuration for community topic sourcing."""
    __tablename__ = 'discord_integrations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # "MouseCast Community", "TechPod Discord"

    # Discord connection settings
    guild_id = db.Column(db.String(50), nullable=False)  # Discord server ID
    channel_id = db.Column(db.String(50), nullable=False)  # Channel to monitor (single mode)

    # Bot token stored in env var - reference by name (never store actual token)
    bot_token_env_var = db.Column(db.String(100), default='DISCORD_BOT_TOKEN')

    # Link to template (each podcast/show has its own template)
    template_id = db.Column(db.Integer, db.ForeignKey('episode_guide_templates.id'), nullable=False, index=True)

    # Scan mode settings
    scan_mode = db.Column(db.String(20), default='single')  # 'single' or 'multi'
    scan_channel_ids = db.Column(db.Text, nullable=True)    # Comma-separated channel IDs for multi mode
    scan_emoji = db.Column(db.String(100), nullable=True)   # Single emoji for multi-channel scan
    scan_target_section = db.Column(db.String(50), nullable=True)  # Target section for multi mode imports

    # Settings
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    template = db.relationship('EpisodeGuideTemplate', backref=db.backref('discord_integration', uselist=False))
    emoji_mappings = db.relationship('DiscordEmojiMapping', back_populates='integration',
                                     cascade='all, delete-orphan', order_by='DiscordEmojiMapping.display_order')
    import_logs = db.relationship('DiscordImportLog', back_populates='integration', cascade='all, delete-orphan')

    def get_bot_token(self):
        """Get the bot token from environment variable."""
        import os
        return os.environ.get(self.bot_token_env_var)

    def get_scan_channel_list(self):
        """Get list of channel IDs for multi-channel scan mode."""
        if not self.scan_channel_ids:
            return []
        return [cid.strip() for cid in self.scan_channel_ids.split(',') if cid.strip()]

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'guild_id': self.guild_id,
            'channel_id': self.channel_id,
            'template_id': self.template_id,
            'template_name': self.template.name if self.template else None,
            'is_active': self.is_active,
            'scan_mode': self.scan_mode or 'single',
            'scan_channel_ids': self.scan_channel_ids,
            'scan_emoji': self.scan_emoji,
            'scan_target_section': self.scan_target_section,
            'emoji_mappings': [m.to_dict() for m in self.emoji_mappings],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DiscordEmojiMapping(db.Model):
    """Maps Discord emoji reactions to episode guide sections."""
    __tablename__ = 'discord_emoji_mappings'

    id = db.Column(db.Integer, primary_key=True)

    # Link to integration (and through it, to template)
    integration_id = db.Column(db.Integer, db.ForeignKey('discord_integrations.id'), nullable=False, index=True)

    # The emoji - supports both Unicode emoji and custom Discord emoji
    # Unicode: "🐭", "📰", "⌨️"
    # Custom: "<:mouselogo:123456789>" (Discord custom emoji format)
    emoji = db.Column(db.String(100), nullable=False)
    emoji_name = db.Column(db.String(50), nullable=True)  # Human-readable name for display

    # Target section key (must exist in template's sections)
    section_key = db.Column(db.String(50), nullable=False)  # e.g., "news_mice", "community_recap"

    # Display order in UI
    display_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    integration = db.relationship('DiscordIntegration', back_populates='emoji_mappings')

    # Unique constraint: one emoji per integration
    __table_args__ = (
        db.UniqueConstraint('integration_id', 'emoji', name='unique_integration_emoji'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'integration_id': self.integration_id,
            'emoji': self.emoji,
            'emoji_name': self.emoji_name,
            'section_key': self.section_key,
            'display_order': self.display_order,
        }


class DiscordImportLog(db.Model):
    """Tracks imported Discord messages to prevent duplicates."""
    __tablename__ = 'discord_import_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Which integration and guide
    integration_id = db.Column(db.Integer, db.ForeignKey('discord_integrations.id'), nullable=False, index=True)
    guide_id = db.Column(db.Integer, db.ForeignKey('episode_guides.id'), nullable=False, index=True)

    # Discord message ID (used to prevent duplicate imports)
    discord_message_id = db.Column(db.String(50), nullable=False, index=True)

    # The created episode guide item
    item_id = db.Column(db.Integer, db.ForeignKey('episode_guide_items.id'), nullable=True)

    # Import metadata
    imported_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    imported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    integration = db.relationship('DiscordIntegration', back_populates='import_logs')
    guide = db.relationship('EpisodeGuide', backref='discord_imports')
    item = db.relationship('EpisodeGuideItem', backref='discord_import')
    user = db.relationship('User', backref='discord_imports')

    # Unique constraint: can't import same message to same guide twice
    __table_args__ = (
        db.UniqueConstraint('guide_id', 'discord_message_id', name='unique_guide_message'),
    )
