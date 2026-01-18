"""
Models package - re-exports all models for backward compatibility.

All existing imports like `from models import User` will continue to work.
For new code, you can import from specific modules:
    from models.auth import User, AuditLog
    from models.business import Company, Contact
"""

# Auth models
from models.auth import User, AuditLog, LoginHistory

# Business/CRM models
from models.business import (
    Contact,
    Company,
    Inventory,
    AffiliateRevenue,
    Collaboration,
    SalesPipeline,
    OutreachTemplate,
)

# Configuration models
from models.config import CustomOption

# Content models
from models.content import (
    EpisodeGuideTemplate,
    EpisodeGuide,
    EpisodeGuideItem,
)

# Media kit models
from models.media_kit import (
    CreatorProfile,
    RateCard,
    Testimonial,
)

# Discord integration models
from models.discord import (
    DiscordIntegration,
    DiscordEmojiMapping,
    DiscordImportLog,
)

# Podcast models
from models.podcast import (
    Podcast,
    PodcastMember,
)

# Export all for backward compatibility
__all__ = [
    # Auth
    'User',
    'AuditLog',
    'LoginHistory',
    # Business
    'Contact',
    'Company',
    'Inventory',
    'AffiliateRevenue',
    'Collaboration',
    'SalesPipeline',
    'OutreachTemplate',
    # Config
    'CustomOption',
    # Content
    'EpisodeGuideTemplate',
    'EpisodeGuide',
    'EpisodeGuideItem',
    # Media Kit
    'CreatorProfile',
    'RateCard',
    'Testimonial',
    # Discord
    'DiscordIntegration',
    'DiscordEmojiMapping',
    'DiscordImportLog',
    # Podcast
    'Podcast',
    'PodcastMember',
]
