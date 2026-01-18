"""Creator Hub models - Revenue, Deliverables, Content Atomizer, Social."""
from datetime import datetime, timezone, date
from extensions import db


class RevenueEntry(db.Model):
    """Unified income tracking across all revenue streams."""
    __tablename__ = 'revenue_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Source categorization
    source_type = db.Column(db.String(50), nullable=False, index=True)
    source_name = db.Column(db.String(255), nullable=False)

    # Links to existing models (optional)
    affiliate_revenue_id = db.Column(db.Integer, db.ForeignKey('affiliate_revenue.id'), nullable=True, index=True)
    pipeline_deal_id = db.Column(db.Integer, db.ForeignKey('sales_pipeline.id'), nullable=True, index=True)

    # Financial
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')

    # Timing
    date_earned = db.Column(db.Date, nullable=False, index=True)
    date_received = db.Column(db.Date, nullable=True)

    # Metadata
    notes = db.Column(db.Text, nullable=True)
    receipt_path = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref='revenue_entries')
    affiliate_revenue = db.relationship('AffiliateRevenue', backref='revenue_entry')
    pipeline_deal = db.relationship('SalesPipeline', backref='revenue_entries')

    # Source type constants
    SOURCE_SPONSORSHIP = 'sponsorship'
    SOURCE_AFFILIATE = 'affiliate'
    SOURCE_PLATFORM = 'platform'
    SOURCE_PRODUCT = 'product'
    SOURCE_MEMBERSHIP = 'membership'
    SOURCE_OTHER = 'other'

    SOURCE_TYPES = [
        (SOURCE_SPONSORSHIP, 'Sponsorship'),
        (SOURCE_AFFILIATE, 'Affiliate'),
        (SOURCE_PLATFORM, 'Platform Payout'),
        (SOURCE_PRODUCT, 'Digital Product'),
        (SOURCE_MEMBERSHIP, 'Membership'),
        (SOURCE_OTHER, 'Other'),
    ]

    @property
    def month_year(self):
        """Return formatted month/year for grouping."""
        if not self.date_earned:
            return None
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return f"{months[self.date_earned.month]} {self.date_earned.year}"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'source_type': self.source_type,
            'source_name': self.source_name,
            'affiliate_revenue_id': self.affiliate_revenue_id,
            'pipeline_deal_id': self.pipeline_deal_id,
            'amount': float(self.amount) if self.amount else 0,
            'currency': self.currency,
            'date_earned': self.date_earned.isoformat() if self.date_earned else None,
            'date_received': self.date_received.isoformat() if self.date_received else None,
            'month_year': self.month_year,
            'notes': self.notes,
            'receipt_path': self.receipt_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DealDeliverable(db.Model):
    """Individual deliverables within a sponsor deal."""
    __tablename__ = 'deal_deliverables'

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('sales_pipeline.id'), nullable=False, index=True)

    # Deliverable details
    deliverable_type = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    # Timeline
    due_date = db.Column(db.Date, nullable=True, index=True)
    completed_date = db.Column(db.Date, nullable=True)

    # Link to actual published content
    platform_post_url = db.Column(db.Text, nullable=True)
    platform_post_id = db.Column(db.String(255), nullable=True)

    # Performance metrics
    impressions = db.Column(db.Integer, nullable=True)
    reach = db.Column(db.Integer, nullable=True)
    engagement = db.Column(db.Integer, nullable=True)
    clicks = db.Column(db.Integer, nullable=True)
    conversions = db.Column(db.Integer, nullable=True)

    # Status tracking
    status = db.Column(db.String(20), default='pending', index=True)

    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    deal = db.relationship('SalesPipeline', backref=db.backref('deliverables_list',
                           cascade='all, delete-orphan', order_by='DealDeliverable.due_date'))

    # Deliverable type constants
    TYPE_YOUTUBE_VIDEO = 'youtube_video'
    TYPE_YOUTUBE_SHORT = 'youtube_short'
    TYPE_INSTAGRAM_POST = 'instagram_post'
    TYPE_INSTAGRAM_STORY = 'instagram_story'
    TYPE_INSTAGRAM_REEL = 'instagram_reel'
    TYPE_TIKTOK_VIDEO = 'tiktok_video'
    TYPE_TWITTER_POST = 'twitter_post'
    TYPE_PODCAST_AD = 'podcast_ad'
    TYPE_PODCAST_EPISODE = 'podcast_episode'
    TYPE_BLOG_POST = 'blog_post'
    TYPE_OTHER = 'other'

    DELIVERABLE_TYPES = [
        (TYPE_YOUTUBE_VIDEO, 'YouTube Video'),
        (TYPE_YOUTUBE_SHORT, 'YouTube Short'),
        (TYPE_INSTAGRAM_POST, 'Instagram Post'),
        (TYPE_INSTAGRAM_STORY, 'Instagram Story'),
        (TYPE_INSTAGRAM_REEL, 'Instagram Reel'),
        (TYPE_TIKTOK_VIDEO, 'TikTok Video'),
        (TYPE_TWITTER_POST, 'Twitter/X Post'),
        (TYPE_PODCAST_AD, 'Podcast Ad Read'),
        (TYPE_PODCAST_EPISODE, 'Podcast Episode'),
        (TYPE_BLOG_POST, 'Blog Post'),
        (TYPE_OTHER, 'Other'),
    ]

    # Status constants
    STATUS_PENDING = 'pending'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_DELIVERED = 'delivered'
    STATUS_VERIFIED = 'verified'

    STATUSES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_VERIFIED, 'Verified'),
    ]

    @property
    def is_overdue(self):
        """Check if deliverable is past due date and not completed."""
        if self.status in (self.STATUS_DELIVERED, self.STATUS_VERIFIED):
            return False
        if not self.due_date:
            return False
        return date.today() > self.due_date

    @property
    def total_engagement(self):
        """Calculate total engagement metrics."""
        return (self.impressions or 0) + (self.engagement or 0) + (self.clicks or 0)

    def to_dict(self):
        return {
            'id': self.id,
            'deal_id': self.deal_id,
            'deliverable_type': self.deliverable_type,
            'description': self.description,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'platform_post_url': self.platform_post_url,
            'platform_post_id': self.platform_post_id,
            'impressions': self.impressions,
            'reach': self.reach,
            'engagement': self.engagement,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'total_engagement': self.total_engagement,
            'status': self.status,
            'is_overdue': self.is_overdue,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ContentAtomicTemplate(db.Model):
    """AI prompt template for generating platform-specific content."""
    __tablename__ = 'content_atomic_templates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Template metadata
    name = db.Column(db.String(100), nullable=False)
    platform = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    # AI prompt configuration
    prompt_template = db.Column(db.Text, nullable=False)
    system_prompt = db.Column(db.Text, nullable=True)
    tone = db.Column(db.String(50), nullable=True)

    # Platform constraints
    max_length = db.Column(db.Integer, nullable=True)
    include_hashtags = db.Column(db.Boolean, default=False)
    include_emoji = db.Column(db.Boolean, default=False)
    include_cta = db.Column(db.Boolean, default=False)

    # Status
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    times_used = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref='atomizer_templates')

    # Platform constants
    PLATFORM_TWITTER = 'twitter'
    PLATFORM_INSTAGRAM = 'instagram'
    PLATFORM_YOUTUBE = 'youtube'
    PLATFORM_LINKEDIN = 'linkedin'
    PLATFORM_TIKTOK = 'tiktok'
    PLATFORM_THREADS = 'threads'
    PLATFORM_FACEBOOK = 'facebook'
    PLATFORM_BLUESKY = 'bluesky'

    PLATFORMS = [
        (PLATFORM_TWITTER, 'Twitter/X', 280),
        (PLATFORM_INSTAGRAM, 'Instagram', 2200),
        (PLATFORM_YOUTUBE, 'YouTube Description', 5000),
        (PLATFORM_LINKEDIN, 'LinkedIn', 3000),
        (PLATFORM_TIKTOK, 'TikTok', 2200),
        (PLATFORM_THREADS, 'Threads', 500),
        (PLATFORM_FACEBOOK, 'Facebook', 63206),
        (PLATFORM_BLUESKY, 'Bluesky', 300),
    ]

    TONES = [
        ('casual', 'Casual'),
        ('professional', 'Professional'),
        ('humorous', 'Humorous'),
        ('inspirational', 'Inspirational'),
        ('educational', 'Educational'),
        ('conversational', 'Conversational'),
    ]

    @classmethod
    def get_platform_limit(cls, platform):
        """Get character limit for a platform."""
        for p, name, limit in cls.PLATFORMS:
            if p == platform:
                return limit
        return None

    @classmethod
    def get_platform_display(cls, platform):
        """Get display name for a platform."""
        for p, name, limit in cls.PLATFORMS:
            if p == platform:
                return name
        return platform.title()

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'platform': self.platform,
            'platform_display': self.get_platform_display(self.platform),
            'description': self.description,
            'prompt_template': self.prompt_template,
            'system_prompt': self.system_prompt,
            'tone': self.tone,
            'max_length': self.max_length,
            'include_hashtags': self.include_hashtags,
            'include_emoji': self.include_emoji,
            'include_cta': self.include_cta,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'times_used': self.times_used,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ContentAtomicSnippet(db.Model):
    """AI-generated platform-optimized content snippet."""
    __tablename__ = 'content_atomic_snippets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Source content reference
    source_type = db.Column(db.String(50), nullable=False, default='manual', index=True)
    source_id = db.Column(db.Integer, nullable=True, index=True)
    source_title = db.Column(db.String(255), nullable=True)

    # Template used
    template_id = db.Column(db.Integer, db.ForeignKey('content_atomic_templates.id'), nullable=True)

    # Content
    platform = db.Column(db.String(50), nullable=False, index=True)
    source_content = db.Column(db.Text, nullable=False)
    generated_content = db.Column(db.Text, nullable=False)
    edited_content = db.Column(db.Text, nullable=True)

    # Metadata
    character_count = db.Column(db.Integer)
    word_count = db.Column(db.Integer)
    hashtags = db.Column(db.JSON, nullable=True)

    # AI details
    ai_model = db.Column(db.String(50), nullable=True)
    ai_temperature = db.Column(db.Float, nullable=True)
    generation_time_ms = db.Column(db.Integer, nullable=True)

    # Status workflow
    status = db.Column(db.String(20), default='draft', index=True)

    # Publishing tracking
    scheduled_date = db.Column(db.DateTime, nullable=True)
    published_date = db.Column(db.DateTime, nullable=True)
    published_url = db.Column(db.Text, nullable=True)

    # User feedback
    rating = db.Column(db.Integer, nullable=True)
    feedback_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref='atomized_snippets')
    template = db.relationship('ContentAtomicTemplate', backref='snippets')

    # Source type constants
    SOURCE_MANUAL = 'manual'
    SOURCE_EPISODE = 'episode'
    SOURCE_TRANSCRIPT = 'transcript'
    SOURCE_BLOG = 'blog'
    SOURCE_NOTES = 'notes'

    SOURCE_TYPES = [
        (SOURCE_MANUAL, 'Manual Input'),
        (SOURCE_EPISODE, 'Episode Guide'),
        (SOURCE_TRANSCRIPT, 'Transcript'),
        (SOURCE_BLOG, 'Blog Post'),
        (SOURCE_NOTES, 'Notes'),
    ]

    # Status constants
    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'

    STATUSES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    @property
    def final_content(self):
        """Return edited content if available, otherwise generated."""
        return self.edited_content or self.generated_content

    @property
    def is_over_limit(self):
        """Check if content exceeds platform limit."""
        limit = ContentAtomicTemplate.get_platform_limit(self.platform)
        if not limit:
            return False
        return len(self.final_content) > limit

    @property
    def platform_display(self):
        """Get display name for platform."""
        return ContentAtomicTemplate.get_platform_display(self.platform)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'source_title': self.source_title,
            'template_id': self.template_id,
            'platform': self.platform,
            'platform_display': self.platform_display,
            'source_content': self.source_content,
            'generated_content': self.generated_content,
            'edited_content': self.edited_content,
            'final_content': self.final_content,
            'character_count': self.character_count,
            'word_count': self.word_count,
            'hashtags': self.hashtags,
            'ai_model': self.ai_model,
            'status': self.status,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'published_date': self.published_date.isoformat() if self.published_date else None,
            'published_url': self.published_url,
            'rating': self.rating,
            'is_over_limit': self.is_over_limit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SocialConnection(db.Model):
    """OAuth connection to a social media platform for posting."""
    __tablename__ = 'social_connections'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Platform identification
    platform = db.Column(db.String(50), nullable=False, index=True)

    # Account info
    platform_user_id = db.Column(db.String(100), nullable=True)
    platform_username = db.Column(db.String(100), nullable=True)

    # Encrypted credentials
    encrypted_credentials = db.Column(db.Text, nullable=False)

    # Token metadata
    token_expires_at = db.Column(db.DateTime, nullable=True)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref='social_connections')

    # Platform constants
    PLATFORM_TWITTER = 'twitter'

    PLATFORMS = [
        (PLATFORM_TWITTER, 'Twitter/X'),
    ]

    __table_args__ = (
        db.UniqueConstraint('user_id', 'platform', name='unique_user_platform'),
    )

    @classmethod
    def get_platform_display(cls, platform):
        """Get display name for a platform."""
        for p, name in cls.PLATFORMS:
            if p == platform:
                return name
        return platform.title()

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'platform': self.platform,
            'platform_display': self.get_platform_display(self.platform),
            'platform_user_id': self.platform_user_id,
            'platform_username': self.platform_username,
            'is_active': self.is_active,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SocialPostLog(db.Model):
    """Log of social media posts for audit trail."""
    __tablename__ = 'social_post_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Links
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    snippet_id = db.Column(db.Integer, db.ForeignKey('content_atomic_snippets.id'), nullable=True, index=True)
    connection_id = db.Column(db.Integer, db.ForeignKey('social_connections.id'), nullable=True)

    # Post details
    platform = db.Column(db.String(50), nullable=False, index=True)
    content_posted = db.Column(db.Text, nullable=False)

    # Result
    success = db.Column(db.Boolean, default=False)
    platform_post_id = db.Column(db.String(100), nullable=True)
    platform_post_url = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    # Timing
    posted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    response_time_ms = db.Column(db.Integer, nullable=True)

    # Relationships
    user = db.relationship('User', backref='social_post_logs')
    snippet = db.relationship('ContentAtomicSnippet', backref='post_logs')
    connection = db.relationship('SocialConnection', backref='post_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'snippet_id': self.snippet_id,
            'connection_id': self.connection_id,
            'platform': self.platform,
            'platform_display': SocialConnection.get_platform_display(self.platform),
            'content_posted': self.content_posted,
            'success': self.success,
            'platform_post_id': self.platform_post_id,
            'platform_post_url': self.platform_post_url,
            'error_message': self.error_message,
            'posted_at': self.posted_at.isoformat() if self.posted_at else None,
            'response_time_ms': self.response_time_ms,
        }
