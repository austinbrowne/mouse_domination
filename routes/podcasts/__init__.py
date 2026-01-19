"""Podcast management routes package.

This package provides:
- Podcast CRUD (list, create, edit, settings)
- Member management (add, remove, change roles)
- Scoped episode and template routes under /podcasts/<id>/
- Discord integration for episode content import
"""
from flask import Blueprint

# Create the blueprint
podcast_bp = Blueprint('podcasts', __name__)

# Import route modules to register their routes with the blueprint
# These imports must come after podcast_bp is created to avoid circular imports
from . import core
from . import members
from . import episodes
from . import items
from . import templates
from . import discord
