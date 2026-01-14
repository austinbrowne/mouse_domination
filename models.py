from datetime import datetime, date, timezone, timedelta
import secrets
from extensions import db
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError


class User(db.Model):
    """Authenticated users with Flask-Login support."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Authentication fields
    password_hash = db.Column(db.String(255), nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)

    # Authorization fields
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

    # Relationships
    inventory_items = db.relationship('Inventory', back_populates='user', lazy='dynamic')

    # Argon2id password hasher (OWASP recommended)
    _ph = PasswordHasher(
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        salt_len=16
    )

    # Flask-Login required properties
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.is_approved

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    # Password methods
    def set_password(self, password: str) -> None:
        """Hash and set password using Argon2id."""
        self.password_hash = self._ph.hash(password)
        self.password_changed_at = datetime.now(timezone.utc)

    def check_password(self, password: str) -> bool:
        """Verify password. Returns False for any error."""
        if not self.password_hash:
            return False
        try:
            self._ph.verify(self.password_hash, password)
            if self._ph.check_needs_rehash(self.password_hash):
                self.password_hash = self._ph.hash(password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False

    def is_locked(self) -> bool:
        """Check if account is locked due to failed attempts."""
        if not self.locked_until:
            return False
        # Handle both naive (from SQLite) and aware datetimes
        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= locked_until:
            self.locked_until = None
            self.failed_login_attempts = 0
            return False
        return True

    def record_failed_login(self) -> None:
        """Record failed login and apply progressive lockout."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= 5:
            lockout_minutes = [5, 15, 60, 1440][min(self.failed_login_attempts - 5, 3)]
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)

    def record_successful_login(self) -> None:
        """Reset failed attempts and update last login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'is_approved': self.is_approved,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }


class Contact(db.Model):
    """People in your network - reviewers, company reps, podcast guests."""
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)  # Index for search
    role = db.Column(db.String(20), default='other', index=True)  # Index for filtering
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    twitter = db.Column(db.String(50), nullable=True)
    discord = db.Column(db.String(50), nullable=True)
    youtube = db.Column(db.String(100), nullable=True)
    relationship_status = db.Column(db.String(20), default='cold', index=True)  # Index for filtering
    notes = db.Column(db.Text, nullable=True)
    last_contact_date = db.Column(db.Date, nullable=True)
    tags = db.Column(db.String(200), nullable=True)  # comma-separated tags
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    company = db.relationship('Company', back_populates='contacts')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'email': self.email,
            'twitter': self.twitter,
            'discord': self.discord,
            'youtube': self.youtube,
            'relationship_status': self.relationship_status,
            'notes': self.notes,
            'last_contact_date': self.last_contact_date.isoformat() if self.last_contact_date else None,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Company(db.Model):
    """Peripheral companies and brands."""
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(20), default='mice', index=True)  # mice, keyboards, mousepads, iems, other
    website = db.Column(db.String(200), nullable=True)
    relationship_status = db.Column(db.String(20), default='no_contact', index=True)  # no_contact, reached_out, active, affiliate_only, past
    affiliate_status = db.Column(db.String(20), default='no', index=True)  # yes, no, pending
    affiliate_code = db.Column(db.String(50), nullable=True)
    affiliate_link = db.Column(db.String(300), nullable=True)
    commission_rate = db.Column(db.Float, nullable=True)  # percentage
    notes = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='low')  # target, active, low
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships - use default lazy='select' for efficient eager loading
    contacts = db.relationship('Contact', back_populates='company', lazy='select')
    inventory_items = db.relationship('Inventory', back_populates='company', lazy='select')
    affiliate_revenues = db.relationship('AffiliateRevenue', back_populates='company', lazy='select')

    def to_dict(self, contact_count: int = None, inventory_count: int = None):
        """Convert to dictionary. Pass counts from service layer to avoid N+1."""
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'website': self.website,
            'relationship_status': self.relationship_status,
            'affiliate_status': self.affiliate_status,
            'affiliate_code': self.affiliate_code,
            'affiliate_link': self.affiliate_link,
            'commission_rate': self.commission_rate,
            'notes': self.notes,
            'priority': self.priority,
            'contact_count': contact_count,
            'inventory_count': inventory_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Inventory(db.Model):
    """Products - both review units and personal purchases."""
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_name = db.Column(db.String(150), nullable=False, index=True)  # Index for search
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    category = db.Column(db.String(20), default='mouse', index=True)  # Index for filtering
    source_type = db.Column(db.String(20), default='review_unit', index=True)
    date_acquired = db.Column(db.Date, nullable=True, index=True)
    cost = db.Column(db.Float, default=0.0)  # $0 for review units
    on_amazon = db.Column(db.Boolean, default=False)
    deadline = db.Column(db.Date, nullable=True, index=True)  # Index for deadline queries
    return_by_date = db.Column(db.Date, nullable=True, index=True)  # When loaner must be returned
    status = db.Column(db.String(20), default='in_queue', index=True)  # Index for filtering
    condition = db.Column(db.String(20), default='new')  # new, open_box, used
    notes = db.Column(db.Text, nullable=True)

    # Content links
    short_url = db.Column(db.String(200), nullable=True)
    short_publish_date = db.Column(db.Date, nullable=True)
    video_url = db.Column(db.String(200), nullable=True)
    video_publish_date = db.Column(db.Date, nullable=True)

    # Sales tracking
    sold = db.Column(db.Boolean, default=False, index=True)  # Index for sold filtering
    sale_price = db.Column(db.Float, nullable=True)
    fees = db.Column(db.Float, nullable=True)
    shipping = db.Column(db.Float, nullable=True)
    marketplace = db.Column(db.String(20), nullable=True)  # ebay, reddit, discord, offerup, mercari, facebook, local, other
    buyer = db.Column(db.String(100), nullable=True)
    sale_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', back_populates='inventory_items')
    company = db.relationship('Company', back_populates='inventory_items')

    @property
    def profit_loss(self):
        """Calculate P/L: sale_price - fees - shipping - cost."""
        if not self.sold or self.sale_price is None:
            return -self.cost if self.cost else 0.0

        sale = self.sale_price or 0.0
        fees = self.fees or 0.0
        shipping = self.shipping or 0.0
        cost = self.cost or 0.0

        return sale - fees - shipping - cost

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_name': self.product_name,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'category': self.category,
            'source_type': self.source_type,
            'date_acquired': self.date_acquired.isoformat() if self.date_acquired else None,
            'cost': self.cost,
            'on_amazon': self.on_amazon,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'return_by_date': self.return_by_date.isoformat() if self.return_by_date else None,
            'status': self.status,
            'condition': self.condition,
            'notes': self.notes,
            'short_url': self.short_url,
            'short_publish_date': self.short_publish_date.isoformat() if self.short_publish_date else None,
            'video_url': self.video_url,
            'video_publish_date': self.video_publish_date.isoformat() if self.video_publish_date else None,
            'sold': self.sold,
            'sale_price': self.sale_price,
            'fees': self.fees,
            'shipping': self.shipping,
            'profit_loss': self.profit_loss,
            'marketplace': self.marketplace,
            'buyer': self.buyer,
            'sale_notes': self.sale_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AffiliateRevenue(db.Model):
    """Monthly affiliate revenue tracking by company."""
    __tablename__ = 'affiliate_revenue'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)  # Index for year filtering
    month = db.Column(db.Integer, nullable=False, index=True)  # Index for month filtering
    revenue = db.Column(db.Float, nullable=False, default=0.0)
    sales_count = db.Column(db.Integer, nullable=True)  # Number of sales if known
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    company = db.relationship('Company', back_populates='affiliate_revenues')

    # Unique constraint: one entry per company per month
    __table_args__ = (
        db.UniqueConstraint('company_id', 'year', 'month', name='unique_company_month'),
    )

    @property
    def month_year(self):
        """Return formatted month/year string."""
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return f"{months[self.month]} {self.year}"

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'year': self.year,
            'month': self.month,
            'month_year': self.month_year,
            'revenue': self.revenue,
            'sales_count': self.sales_count,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Collaboration(db.Model):
    """Track cross-promos, guest appearances, and outreach."""
    __tablename__ = 'collaborations'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False, index=True)
    collab_type = db.Column(db.String(30), default='collab_video', index=True)
    # Types: guest_on_their_channel, guest_on_mousecast, cross_promo, collab_video
    status = db.Column(db.String(20), default='idea', index=True)
    # Status: idea, reached_out, confirmed, completed, declined
    scheduled_date = db.Column(db.Date, nullable=True, index=True)
    completed_date = db.Column(db.Date, nullable=True)
    their_channel = db.Column(db.String(200), nullable=True)
    their_platform = db.Column(db.String(50), nullable=True)  # youtube, twitter, twitch, etc.
    audience_size = db.Column(db.Integer, nullable=True)
    result_views = db.Column(db.Integer, nullable=True)
    result_new_subs = db.Column(db.Integer, nullable=True)
    result_notes = db.Column(db.Text, nullable=True)
    follow_up_needed = db.Column(db.Boolean, default=False, index=True)
    follow_up_date = db.Column(db.Date, nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    contact = db.relationship('Contact', backref='collaborations')

    def to_dict(self):
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'contact_name': self.contact.name if self.contact else None,
            'collab_type': self.collab_type,
            'status': self.status,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'their_channel': self.their_channel,
            'their_platform': self.their_platform,
            'audience_size': self.audience_size,
            'result_views': self.result_views,
            'result_new_subs': self.result_new_subs,
            'result_notes': self.result_notes,
            'follow_up_needed': self.follow_up_needed,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SalesPipeline(db.Model):
    """Track potential and active sponsorship deals."""
    __tablename__ = 'sales_pipeline'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)
    deal_type = db.Column(db.String(30), default='paid_review', index=True)
    # Types: paid_review, podcast_ad, sponsored_segment, other
    status = db.Column(db.String(20), default='lead', index=True)
    # Status: lead, negotiating, confirmed, completed, lost
    rate_quoted = db.Column(db.Float, nullable=True)
    rate_agreed = db.Column(db.Float, nullable=True)
    deliverables = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.Date, nullable=True, index=True)
    deliverable_date = db.Column(db.Date, nullable=True, index=True)  # When deliverables are due
    payment_status = db.Column(db.String(20), default='pending', index=True)
    # Payment: pending, invoiced, paid
    payment_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    follow_up_needed = db.Column(db.Boolean, default=False, index=True)
    follow_up_date = db.Column(db.Date, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    company = db.relationship('Company', backref='deals')
    contact = db.relationship('Contact', backref='deals')

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'contact_id': self.contact_id,
            'contact_name': self.contact.name if self.contact else None,
            'deal_type': self.deal_type,
            'status': self.status,
            'rate_quoted': self.rate_quoted,
            'rate_agreed': self.rate_agreed,
            'deliverables': self.deliverables,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'deliverable_date': self.deliverable_date.isoformat() if self.deliverable_date else None,
            'payment_status': self.payment_status,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'notes': self.notes,
            'follow_up_needed': self.follow_up_needed,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class OutreachTemplate(db.Model):
    """Email/message templates for sponsors, collabs, and outreach."""
    __tablename__ = 'outreach_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(30), default='sponsor', index=True)
    # Categories: sponsor, collab, follow_up, thank_you, pitch, other
    subject = db.Column(db.String(200), nullable=True)  # For emails
    body = db.Column(db.Text, nullable=False)
    # Placeholders: {{contact_name}}, {{company_name}}, {{my_channel}}, {{my_stats}}, etc.
    notes = db.Column(db.Text, nullable=True)
    times_used = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'subject': self.subject,
            'body': self.body,
            'notes': self.notes,
            'times_used': self.times_used,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CustomOption(db.Model):
    """User-defined custom options for dropdowns (supplements built-in defaults)."""
    __tablename__ = 'custom_options'

    id = db.Column(db.Integer, primary_key=True)
    option_type = db.Column(db.String(50), nullable=False, index=True)
    # Types: inventory_category, inventory_status, company_category, collab_type, deal_type, contact_role
    value = db.Column(db.String(100), nullable=False)  # e.g., 'flashlight'
    label = db.Column(db.String(100), nullable=False)  # e.g., 'Flashlight'
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Unique constraint: one value per option_type
    __table_args__ = (
        db.UniqueConstraint('option_type', 'value', name='unique_option_type_value'),
    )

    # Relationship
    creator = db.relationship('User', backref='custom_options')

    def to_dict(self):
        return {
            'id': self.id,
            'option_type': self.option_type,
            'value': self.value,
            'label': self.label,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EpisodeGuideTemplate(db.Model):
    """Reusable template for episode guides with default sections and static content."""
    __tablename__ = 'episode_guide_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

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

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
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
        from constants import EPISODE_GUIDE_SECTIONS

        # Start with builtin sections
        sections = list(EPISODE_GUIDE_SECTIONS)

        # Add custom sections from this guide
        if self.custom_sections:
            for cs in self.custom_sections:
                sections.append((cs['key'], cs['name'], cs.get('parent')))

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


class CreatorProfile(db.Model):
    """Creator's public profile for media kit generation."""
    __tablename__ = 'creator_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)

    # Basic Info
    display_name = db.Column(db.String(100), nullable=False)
    tagline = db.Column(db.String(200), nullable=True)  # "Tech reviewer specializing in gaming peripherals"
    bio = db.Column(db.Text, nullable=True)  # 2-3 sentences about you
    photo_url = db.Column(db.String(500), nullable=True)  # Profile photo URL or path
    location = db.Column(db.String(100), nullable=True)  # "Austin, TX"

    # Contact
    contact_email = db.Column(db.String(255), nullable=True)
    website_url = db.Column(db.String(500), nullable=True)

    # Social Platforms (JSON for flexibility)
    # Format: {"youtube": "@handle", "twitter": "@handle", "instagram": "@handle", ...}
    social_links = db.Column(db.JSON, nullable=True)

    # Platform Stats (JSON - updated periodically)
    # Format: {"youtube": {"subscribers": 4500, "avg_views": 2000, "engagement_rate": 8.2}, ...}
    platform_stats = db.Column(db.JSON, nullable=True)

    # Audience Demographics (JSON)
    # Format: {"age": {"18-24": 35, "25-34": 45, ...}, "gender": {"male": 72, "female": 28}, "top_locations": ["US", "UK", "Canada"]}
    audience_demographics = db.Column(db.JSON, nullable=True)

    # Content Niche/Topics (JSON array)
    # Format: ["gaming peripherals", "tech reviews", "podcasting"]
    content_niches = db.Column(db.JSON, nullable=True)

    # Public sharing
    public_token = db.Column(db.String(64), unique=True, nullable=True, index=True)  # For shareable link
    is_public = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref=db.backref('creator_profile', uselist=False))
    rate_cards = db.relationship('RateCard', back_populates='profile', cascade='all, delete-orphan',
                                 order_by='RateCard.display_order')
    testimonials = db.relationship('Testimonial', back_populates='profile', cascade='all, delete-orphan',
                                   order_by='Testimonial.created_at.desc()')

    def generate_public_token(self):
        """Generate a new public token for sharing."""
        self.public_token = secrets.token_urlsafe(48)  # 64 chars
        return self.public_token

    def get_total_followers(self):
        """Calculate total followers across all platforms."""
        if not self.platform_stats:
            return 0
        total = 0
        for platform, stats in self.platform_stats.items():
            if isinstance(stats, dict):
                total += stats.get('subscribers', 0) or stats.get('followers', 0) or 0
        return total

    def get_avg_engagement_rate(self):
        """Calculate average engagement rate across platforms."""
        if not self.platform_stats:
            return None
        rates = []
        for platform, stats in self.platform_stats.items():
            if isinstance(stats, dict) and stats.get('engagement_rate'):
                rates.append(stats['engagement_rate'])
        return sum(rates) / len(rates) if rates else None

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'display_name': self.display_name,
            'tagline': self.tagline,
            'bio': self.bio,
            'photo_url': self.photo_url,
            'location': self.location,
            'contact_email': self.contact_email,
            'website_url': self.website_url,
            'social_links': self.social_links,
            'platform_stats': self.platform_stats,
            'audience_demographics': self.audience_demographics,
            'content_niches': self.content_niches,
            'public_token': self.public_token,
            'is_public': self.is_public,
            'total_followers': self.get_total_followers(),
            'avg_engagement_rate': self.get_avg_engagement_rate(),
            'rate_card_count': len(self.rate_cards) if self.rate_cards else 0,
            'testimonial_count': len(self.testimonials) if self.testimonials else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class RateCard(db.Model):
    """Pricing for creator services in the media kit."""
    __tablename__ = 'rate_cards'

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('creator_profiles.id'), nullable=False, index=True)

    service_name = db.Column(db.String(100), nullable=False)  # "Sponsored Video"
    description = db.Column(db.Text, nullable=True)  # "Full video review with product showcase"
    price_min = db.Column(db.Numeric(10, 2), nullable=True)  # Starting at
    price_max = db.Column(db.Numeric(10, 2), nullable=True)  # Up to (for ranges)
    price_note = db.Column(db.String(200), nullable=True)  # "Price varies by scope"
    is_negotiable = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    profile = db.relationship('CreatorProfile', back_populates='rate_cards')

    @property
    def price_display(self):
        """Format price for display."""
        if self.price_min and self.price_max:
            return f"${self.price_min:,.0f} - ${self.price_max:,.0f}"
        elif self.price_min:
            return f"${self.price_min:,.0f}+"
        elif self.price_max:
            return f"Up to ${self.price_max:,.0f}"
        elif self.price_note:
            return self.price_note
        return "Contact for pricing"

    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'service_name': self.service_name,
            'description': self.description,
            'price_min': float(self.price_min) if self.price_min else None,
            'price_max': float(self.price_max) if self.price_max else None,
            'price_note': self.price_note,
            'price_display': self.price_display,
            'is_negotiable': self.is_negotiable,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Testimonial(db.Model):
    """Brand testimonials for the media kit."""
    __tablename__ = 'testimonials'

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('creator_profiles.id'), nullable=False, index=True)

    # Company reference (can link to existing company or enter manually)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    company_name = db.Column(db.String(100), nullable=True)  # Manual entry if no company link

    # Contact info
    contact_name = db.Column(db.String(100), nullable=True)
    contact_title = db.Column(db.String(100), nullable=True)  # "Marketing Manager"

    # The testimonial itself
    quote = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    profile = db.relationship('CreatorProfile', back_populates='testimonials')
    company = db.relationship('Company', backref='testimonials')

    @property
    def display_company_name(self):
        """Get company name from linked company or manual entry."""
        if self.company:
            return self.company.name
        return self.company_name or "Anonymous"

    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'company_id': self.company_id,
            'company_name': self.display_company_name,
            'contact_name': self.contact_name,
            'contact_title': self.contact_title,
            'quote': self.quote,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ---- Discord Integration for Community Topic Sourcing ----

class DiscordIntegration(db.Model):
    """Discord channel configuration for community topic sourcing."""
    __tablename__ = 'discord_integrations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # "MouseCast Community", "TechPod Discord"

    # Discord connection settings
    guild_id = db.Column(db.String(50), nullable=False)  # Discord server ID
    channel_id = db.Column(db.String(50), nullable=False)  # Channel to monitor

    # Bot token stored in env var - reference by name (never store actual token)
    bot_token_env_var = db.Column(db.String(100), default='DISCORD_BOT_TOKEN')

    # Link to template (each podcast/show has its own template)
    template_id = db.Column(db.Integer, db.ForeignKey('episode_guide_templates.id'), nullable=False, index=True)

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

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'guild_id': self.guild_id,
            'channel_id': self.channel_id,
            'template_id': self.template_id,
            'template_name': self.template.name if self.template else None,
            'is_active': self.is_active,
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
