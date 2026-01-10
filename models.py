from datetime import datetime, date, timezone
from app import db


class Contact(db.Model):
    """People in your network - reviewers, company reps, podcast guests."""
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='other')  # reviewer, company_rep, podcast_guest, other
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    twitter = db.Column(db.String(50), nullable=True)
    discord = db.Column(db.String(50), nullable=True)
    youtube = db.Column(db.String(100), nullable=True)
    relationship_status = db.Column(db.String(20), default='cold')  # cold, warm, active, close
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

    # Relationships
    contacts = db.relationship('Contact', back_populates='company')
    inventory_items = db.relationship('Inventory', back_populates='company')

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
            'contact_count': len(self.contacts),
            'inventory_count': len(self.inventory_items),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Inventory(db.Model):
    """Products - both review units and personal purchases."""
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    category = db.Column(db.String(20), default='mouse')  # mouse, keyboard, mousepad, iem, other
    source_type = db.Column(db.String(20), default='review_unit')  # review_unit, personal_purchase
    date_acquired = db.Column(db.Date, nullable=True)
    cost = db.Column(db.Float, default=0.0)  # $0 for review units
    on_amazon = db.Column(db.Boolean, default=False)
    deadline = db.Column(db.Date, nullable=True)  # optional, for hard deadlines
    status = db.Column(db.String(20), default='in_queue')  # in_queue, reviewing, reviewed, keeping, listed, sold
    condition = db.Column(db.String(20), default='new')  # new, open_box, used
    notes = db.Column(db.Text, nullable=True)

    # Content links
    short_url = db.Column(db.String(200), nullable=True)
    short_publish_date = db.Column(db.Date, nullable=True)
    video_url = db.Column(db.String(200), nullable=True)
    video_publish_date = db.Column(db.Date, nullable=True)

    # Sales tracking
    sold = db.Column(db.Boolean, default=False)
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
