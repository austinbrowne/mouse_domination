"""Centralized constants and choices for the application."""

# Contact choices
CONTACT_ROLE_CHOICES = ['reviewer', 'company_rep', 'podcast_guest', 'other']
CONTACT_STATUS_CHOICES = ['cold', 'warm', 'active', 'close']

# Company choices
COMPANY_CATEGORY_CHOICES = ['mice', 'keyboards', 'mousepads', 'iems', 'other']
COMPANY_STATUS_CHOICES = ['no_contact', 'reached_out', 'active', 'affiliate_only', 'past']
COMPANY_PRIORITY_CHOICES = ['target', 'active', 'low']
AFFILIATE_STATUS_CHOICES = ['yes', 'no', 'pending']

# Inventory choices
INVENTORY_CATEGORY_CHOICES = ['mouse', 'keyboard', 'mousepad', 'iem', 'other']
INVENTORY_SOURCE_TYPE_CHOICES = ['review_unit', 'personal_purchase']
INVENTORY_STATUS_CHOICES = ['in_queue', 'reviewing', 'reviewed', 'keeping', 'listed', 'sold']
INVENTORY_CONDITION_CHOICES = ['new', 'open_box', 'used']
MARKETPLACE_CHOICES = ['ebay', 'reddit', 'discord', 'facebook', 'offerup', 'mercari', 'local', 'other']

# Collaboration choices
COLLAB_TYPE_CHOICES = ['guest_on_their_channel', 'guest_on_mousecast', 'cross_promo', 'collab_video']
COLLAB_STATUS_CHOICES = ['idea', 'reached_out', 'confirmed', 'completed', 'declined']
PLATFORM_CHOICES = ['youtube', 'twitter', 'twitch', 'discord', 'instagram', 'tiktok', 'other']

# Sales Pipeline choices
DEAL_TYPE_CHOICES = ['paid_review', 'podcast_ad', 'sponsored_segment', 'other']
DEAL_STATUS_CHOICES = ['lead', 'negotiating', 'confirmed', 'completed', 'lost']
PAYMENT_STATUS_CHOICES = ['pending', 'invoiced', 'paid']

# Outreach Template choices
TEMPLATE_CATEGORY_CHOICES = ['sponsor', 'collab', 'follow_up', 'thank_you', 'pitch', 'other']

# Pagination defaults
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# Built-in choices lookup for dynamic options system
# Maps option_type to list of (value, label) tuples
BUILTIN_CHOICES = {
    'inventory_category': [
        ('mouse', 'Mouse'),
        ('keyboard', 'Keyboard'),
        ('mousepad', 'Mousepad'),
        ('iem', 'IEM'),
        ('other', 'Other'),
    ],
    'inventory_status': [
        ('in_queue', 'In Queue'),
        ('reviewing', 'Reviewing'),
        ('reviewed', 'Reviewed'),
        ('keeping', 'Keeping'),
        ('listed', 'Listed'),
        ('sold', 'Sold'),
    ],
    'company_category': [
        ('mice', 'Mice'),
        ('keyboards', 'Keyboards'),
        ('mousepads', 'Mousepads'),
        ('iems', 'IEMs'),
        ('other', 'Other'),
    ],
    'collab_type': [
        ('guest_on_their_channel', 'Guest on Their Channel'),
        ('guest_on_mousecast', 'Guest on MouseCast'),
        ('cross_promo', 'Cross Promo'),
        ('collab_video', 'Collab Video'),
    ],
    'deal_type': [
        ('paid_review', 'Paid Review'),
        ('podcast_ad', 'Podcast Ad'),
        ('sponsored_segment', 'Sponsored Segment'),
        ('other', 'Other'),
    ],
    'contact_role': [
        ('reviewer', 'Reviewer'),
        ('company_rep', 'Company Rep'),
        ('podcast_guest', 'Podcast Guest'),
        ('other', 'Other'),
    ],
}

# Option type display names for admin UI
OPTION_TYPE_LABELS = {
    'inventory_category': 'Inventory Category',
    'inventory_status': 'Inventory Status',
    'company_category': 'Company Category',
    'collab_type': 'Collaboration Type',
    'deal_type': 'Deal Type',
    'contact_role': 'Contact Role',
}

# Episode Guide sections (key, display_name, parent_section)
# parent_section is used for grouping subsections under a main section
EPISODE_GUIDE_SECTIONS = [
    ('introduction', 'Introduction', None),
    ('news_mice', 'Mice', 'news'),
    ('news_other', 'Other', 'news'),
    ('news_pads', 'Pads', 'news'),
    ('news_keyboards', 'Keyboards', 'news'),
    ('community_recap', 'Community Recap', None),
    ('personal_ramblings', 'Personal Ramblings', None),
    ('outro', 'Outro', None),
]

# Static content for Introduction section
INTRO_STATIC_CONTENT = [
    "Hello everyone! I'm Phalanges. (and I'm dazztrazak) Welcome to MouseCast",
    "Subscribe",
    "Discord - https://discord.gg/xPFzjD8r",
    "What mice do you have inbound? & What's on your desk right now?",
]

# Static content for Outro section
OUTRO_STATIC_CONTENT = [
    "Thank you all for listening.",
    "MouseCast next week - [UPDATE DATE/TIME]",
    "Like & share the video, it helps the algorithm.",
    "If you have a question or want to submit a discussion topic, leave it in the comments!",
    "We'll be back next Friday with another episode.",
]

# Helper lookups for Episode Guide
EPISODE_GUIDE_SECTION_CHOICES = [s[0] for s in EPISODE_GUIDE_SECTIONS]
EPISODE_GUIDE_SECTION_NAMES = {s[0]: s[1] for s in EPISODE_GUIDE_SECTIONS}
EPISODE_GUIDE_SECTION_PARENTS = {s[0]: s[2] for s in EPISODE_GUIDE_SECTIONS}

# Episode Guide status choices
EPISODE_GUIDE_STATUS_CHOICES = ['draft', 'recording', 'completed']

# Calendar event colors
EVENT_COLORS = {
    'inventory_deadline': '#ef4444',     # Red
    'inventory_return': '#f97316',       # Orange
    'episode': '#3b82f6',                # Blue
    'pipeline_deadline': '#22c55e',      # Green
    'pipeline_deliverable': '#14b8a6',   # Teal
    'pipeline_payment': '#8b5cf6',       # Purple
    'collab': '#ec4899',                 # Pink
    'follow_up': '#6b7280',              # Gray
}

# Rate limiting constants
RATE_LIMITS = {
    'login': '5 per minute',
    '2fa_verify': '10 per minute',
    'register': '3 per hour',
    'forgot_password': '3 per hour',
    'reset_password': '5 per minute',
    'verify_email': '10 per minute',
    'resend_verification': '3 per hour',
}

# Session keys for 2FA flow
SESSION_KEY_2FA_USER_ID = '2fa_user_id'
SESSION_KEY_2FA_REMEMBER = '2fa_remember'
SESSION_KEY_2FA_NEXT = '2fa_next'

# Password requirements
MIN_PASSWORD_LENGTH = 12
PASSWORD_SPECIAL_CHARS = '!@#$%^&*()_+-=[]{}|;:,.<>?'

# Account lockout settings
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATIONS_MINUTES = [5, 15, 60, 1440]  # Progressive lockout
