from datetime import datetime, date, timezone
from app import db


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
    category = db.Column(db.String(20), default='mice')  # mice, keyboards, mousepads, iems, other
    website = db.Column(db.String(200), nullable=True)
    relationship_status = db.Column(db.String(20), default='no_contact')  # no_contact, reached_out, active, affiliate_only, past
    affiliate_status = db.Column(db.String(20), default='no')  # yes, no, pending
    affiliate_code = db.Column(db.String(50), nullable=True)
    affiliate_link = db.Column(db.String(300), nullable=True)
    commission_rate = db.Column(db.Float, nullable=True)  # percentage
    notes = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='low')  # target, active, low
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships with lazy loading options
    contacts = db.relationship('Contact', back_populates='company', lazy='dynamic')
    inventory_items = db.relationship('Inventory', back_populates='company', lazy='dynamic')
    videos = db.relationship('Video', back_populates='company', lazy='dynamic')
    affiliate_revenues = db.relationship('AffiliateRevenue', back_populates='company', lazy='dynamic')

    def to_dict(self):
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
            'contact_count': self.contacts.count(),
            'inventory_count': self.inventory_items.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Inventory(db.Model):
    """Products - both review units and personal purchases."""
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150), nullable=False, index=True)  # Index for search
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    category = db.Column(db.String(20), default='mouse', index=True)  # Index for filtering
    source_type = db.Column(db.String(20), default='review_unit', index=True)
    date_acquired = db.Column(db.Date, nullable=True, index=True)
    cost = db.Column(db.Float, default=0.0)  # $0 for review units
    on_amazon = db.Column(db.Boolean, default=False)
    deadline = db.Column(db.Date, nullable=True, index=True)  # Index for deadline queries
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
            'product_name': self.product_name,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'category': self.category,
            'source_type': self.source_type,
            'date_acquired': self.date_acquired.isoformat() if self.date_acquired else None,
            'cost': self.cost,
            'on_amazon': self.on_amazon,
            'deadline': self.deadline.isoformat() if self.deadline else None,
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


# Association table for Video <-> Inventory many-to-many
video_inventory = db.Table('video_inventory',
    db.Column('video_id', db.Integer, db.ForeignKey('videos.id'), primary_key=True),
    db.Column('inventory_id', db.Integer, db.ForeignKey('inventory.id'), primary_key=True)
)

# Association table for PodcastEpisode <-> Contact (guests) many-to-many
episode_guests = db.Table('episode_guests',
    db.Column('episode_id', db.Integer, db.ForeignKey('podcast_episodes.id'), primary_key=True),
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True)
)


class Video(db.Model):
    """YouTube videos - reviews, comparisons, guides, etc."""
    __tablename__ = 'videos'

    id = db.Column(db.Integer, primary_key=True)

    # YouTube API fields (auto-synced)
    youtube_id = db.Column(db.String(20), unique=True, nullable=True, index=True)  # Index for lookups
    title = db.Column(db.String(200), nullable=False, index=True)  # Index for search
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(300), nullable=True)
    thumbnail_url = db.Column(db.String(300), nullable=True)
    publish_date = db.Column(db.Date, nullable=True)
    duration = db.Column(db.String(20), nullable=True)  # ISO 8601 duration
    views = db.Column(db.Integer, nullable=True)
    likes = db.Column(db.Integer, nullable=True)
    comments = db.Column(db.Integer, nullable=True)
    last_synced = db.Column(db.DateTime, nullable=True)

    # Business metadata (manual entry)
    video_type = db.Column(db.String(20), default='review', index=True)  # Index for filtering
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    sponsored = db.Column(db.Boolean, default=False, index=True)  # Index for filtering
    sponsor_amount = db.Column(db.Float, nullable=True)
    affiliate_links = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    is_podcast = db.Column(db.Boolean, default=False)  # Flag for MouseCast episodes
    is_short = db.Column(db.Boolean, default=False)  # YouTube Shorts

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    company = db.relationship('Company', back_populates='videos')
    products = db.relationship('Inventory', secondary=video_inventory, backref='videos')

    def to_dict(self):
        return {
            'id': self.id,
            'youtube_id': self.youtube_id,
            'title': self.title,
            'description': self.description,
            'url': self.url,
            'thumbnail_url': self.thumbnail_url,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'duration': self.duration,
            'views': self.views,
            'likes': self.likes,
            'comments': self.comments,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None,
            'video_type': self.video_type,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'sponsored': self.sponsored,
            'sponsor_amount': self.sponsor_amount,
            'affiliate_links': self.affiliate_links,
            'notes': self.notes,
            'is_podcast': self.is_podcast,
            'is_short': self.is_short,
            'product_count': len(self.products) if self.products else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PodcastEpisode(db.Model):
    """MouseCast podcast episodes."""
    __tablename__ = 'podcast_episodes'

    id = db.Column(db.Integer, primary_key=True)
    episode_number = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(200), nullable=False)
    publish_date = db.Column(db.Date, nullable=True)
    youtube_url = db.Column(db.String(300), nullable=True)
    topics = db.Column(db.Text, nullable=True)  # Comma-separated or free text
    sponsored = db.Column(db.Boolean, default=False)
    sponsor_name = db.Column(db.String(100), nullable=True)
    sponsor_amount = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    guests = db.relationship('Contact', secondary=episode_guests, backref='podcast_appearances')

    def to_dict(self):
        return {
            'id': self.id,
            'episode_number': self.episode_number,
            'title': self.title,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'youtube_url': self.youtube_url,
            'topics': self.topics,
            'sponsored': self.sponsored,
            'sponsor_name': self.sponsor_name,
            'sponsor_amount': self.sponsor_amount,
            'notes': self.notes,
            'guest_names': [g.name for g in self.guests],
            'guest_count': len(self.guests),
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
