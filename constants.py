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

# Video choices
VIDEO_TYPE_CHOICES = ['review', 'comparison', 'guide', 'tierlist', 'other']

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
