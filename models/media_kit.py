"""Media kit models - creator profiles, rate cards, testimonials."""
from datetime import datetime, timezone
import secrets
from extensions import db


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
