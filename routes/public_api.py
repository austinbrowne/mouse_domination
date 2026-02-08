"""Public API for dazztrazak.com — read-only product/company/profile data.

Base URL: /api/v1/public
Auth:     X-API-Key header (constant-time verified)
Rate:     60 req/min per endpoint
Format:   JSON responses, CSRF exempt
"""
import hmac
import re
from functools import wraps

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy.orm import joinedload
from extensions import limiter
from models.business import Inventory, Company
from models.media_kit import CreatorProfile

_SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

public_api_bp = Blueprint('public_api', __name__)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def require_api_key(f):
    """Verify X-API-Key header using constant-time comparison."""
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = current_app.config.get('PUBLIC_API_KEY', '')
        if not expected:
            return jsonify({'error': 'API not configured'}), 503
        provided = request.headers.get('X-API-Key', '')
        if not hmac.compare_digest(provided, expected):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Error handlers (blueprint-scoped)
# ---------------------------------------------------------------------------

@public_api_bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@public_api_bp.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Rate limit exceeded'}), 429


@public_api_bp.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@public_api_bp.route('/products')
@limiter.limit("60/minute")
@require_api_key
def list_products():
    """List published products, optionally filtered by pick_category."""
    query = Inventory.query.options(joinedload(Inventory.company)).filter_by(is_published=True)

    pick_category = request.args.get('pick_category')
    if pick_category:
        query = query.filter_by(pick_category=pick_category)

    products = query.all()
    return jsonify([p.to_public_dict() for p in products])


@public_api_bp.route('/products/<slug>')
@limiter.limit("60/minute")
@require_api_key
def get_product(slug):
    """Get a single published product by slug."""
    if not _SLUG_RE.match(slug) or len(slug) > 200:
        return jsonify({'error': 'Not found'}), 404
    product = Inventory.query.options(joinedload(Inventory.company)).filter_by(slug=slug, is_published=True).first()
    if not product:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(product.to_public_dict())


@public_api_bp.route('/companies')
@limiter.limit("60/minute")
@require_api_key
def list_companies():
    """List companies with active affiliate status."""
    companies = Company.query.filter_by(affiliate_status='yes').all()
    return jsonify([c.to_public_dict() for c in companies])


@public_api_bp.route('/creator-profile')
@limiter.limit("60/minute")
@require_api_key
def get_creator_profile():
    """Get the first public creator profile."""
    profile = CreatorProfile.query.filter_by(is_public=True).first()
    if not profile:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(profile.to_public_dict())
