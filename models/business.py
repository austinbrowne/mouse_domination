"""Business and CRM models - contacts, companies, inventory, collaborations, etc."""
from datetime import datetime, timezone
from extensions import db


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

    def to_dict(self, include_company=None):
        """Serialize contact. Pass pre-loaded company to avoid N+1 queries."""
        # Use provided company or fall back to relationship (may cause N+1 if not eager loaded)
        company = include_company if include_company is not None else self.company
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'company_id': self.company_id,
            'company_name': company.name if company else None,
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

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # Index for sorting
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

    def to_dict(self, include_company=None):
        """Serialize inventory item. Pass pre-loaded company to avoid N+1 queries."""
        # Use provided company or fall back to relationship (may cause N+1 if not eager loaded)
        company = include_company if include_company is not None else self.company
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_name': self.product_name,
            'company_id': self.company_id,
            'company_name': company.name if company else None,
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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)  # Index for year filtering
    month = db.Column(db.Integer, nullable=False, index=True)  # Index for month filtering
    revenue = db.Column(db.Float, nullable=False, default=0.0)
    sales_count = db.Column(db.Integer, nullable=True)  # Number of sales if known
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref='affiliate_revenues')
    company = db.relationship('Company', back_populates='affiliate_revenues')

    # Unique constraint: one entry per user per company per month
    __table_args__ = (
        db.UniqueConstraint('user_id', 'company_id', 'year', 'month', name='unique_user_company_month'),
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
            'user_id': self.user_id,
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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
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
    user = db.relationship('User', backref='collaborations')
    contact = db.relationship('Contact', backref='collaborations')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
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

    # Performance report (generated from deliverables)
    performance_report = db.Column(db.JSON, nullable=True)
    report_generated_at = db.Column(db.DateTime, nullable=True)

    follow_up_needed = db.Column(db.Boolean, default=False, index=True)
    follow_up_date = db.Column(db.Date, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', backref='deals')
    company = db.relationship('Company', backref='deals')
    contact = db.relationship('Contact', backref='deals')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
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
            'performance_report': self.performance_report,
            'report_generated_at': self.report_generated_at.isoformat() if self.report_generated_at else None,
            'deliverables_count': len(self.deliverables_list) if hasattr(self, 'deliverables_list') and self.deliverables_list else 0,
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
