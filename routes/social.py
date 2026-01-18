"""Social media integration routes for Twitter/X posting.

Handles:
- OAuth 2.0 connection flow with PKCE
- Account management (connect/disconnect)
- Posting content to Twitter
- Post history/logs
"""

import logging
import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user

from extensions import db, limiter
from models import SocialConnection, SocialPostLog, ContentAtomicSnippet
from services.social_posting import (
    SocialPostingService,
    SocialPostingError,
    PlatformAPIError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)

social_bp = Blueprint('social', __name__)


def get_twitter_redirect_uri():
    """Get the OAuth redirect URI for Twitter callback."""
    return url_for('social.twitter_callback', _external=True)


# =============================================================================
# Connection Management
# =============================================================================

@social_bp.route('/connections')
@login_required
def connections():
    """List connected social accounts."""
    twitter_connection = SocialConnection.query.filter_by(
        user_id=current_user.id,
        platform='twitter',
        is_active=True
    ).first()

    service = SocialPostingService()

    return render_template(
        'social/connections.html',
        twitter_connection=twitter_connection,
        twitter_configured=service.is_twitter_configured,
    )


@social_bp.route('/connect/twitter')
@login_required
def connect_twitter():
    """Start Twitter OAuth 2.0 flow."""
    service = SocialPostingService()

    if not service.is_twitter_configured:
        flash('Twitter API is not configured. Please contact the administrator.', 'error')
        return redirect(url_for('social.connections'))

    # Generate PKCE pair
    code_verifier, code_challenge = service.generate_pkce_pair()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store in session for callback verification
    session['twitter_oauth_state'] = state
    session['twitter_oauth_verifier'] = code_verifier

    # Build authorization URL
    redirect_uri = get_twitter_redirect_uri()
    auth_url = service.get_twitter_authorize_url(redirect_uri, state, code_challenge)

    return redirect(auth_url)


@social_bp.route('/callback/twitter')
@login_required
def twitter_callback():
    """Handle Twitter OAuth callback."""
    # Get authorization code and state from query params
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        error_desc = request.args.get('error_description', 'Unknown error')
        flash(f'Twitter authorization failed: {error_desc}', 'error')
        return redirect(url_for('social.connections'))

    if not code:
        flash('No authorization code received from Twitter.', 'error')
        return redirect(url_for('social.connections'))

    # Verify state (CSRF protection)
    expected_state = session.pop('twitter_oauth_state', None)
    if not expected_state or state != expected_state:
        flash('Invalid state parameter. Please try connecting again.', 'error')
        return redirect(url_for('social.connections'))

    # Get code verifier from session
    code_verifier = session.pop('twitter_oauth_verifier', None)
    if not code_verifier:
        flash('Session expired. Please try connecting again.', 'error')
        return redirect(url_for('social.connections'))

    service = SocialPostingService()
    redirect_uri = get_twitter_redirect_uri()

    try:
        # Exchange code for tokens
        token_data = service.exchange_twitter_code(code, redirect_uri, code_verifier)

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 7200)

        if not access_token:
            flash('Failed to get access token from Twitter.', 'error')
            return redirect(url_for('social.connections'))

        # Fetch user info
        user_info = service.get_twitter_user_info(access_token)
        platform_user_id = user_info.get('id')
        platform_username = user_info.get('username')

        if not platform_user_id:
            flash('Failed to fetch user info from Twitter.', 'error')
            return redirect(url_for('social.connections'))

        # Store credentials
        credentials = {
            'access_token': access_token,
            'refresh_token': refresh_token,
        }

        service.create_connection(
            user_id=current_user.id,
            platform='twitter',
            platform_user_id=platform_user_id,
            platform_username=platform_username,
            credentials=credentials,
            expires_in=expires_in,
        )

        flash(f'Successfully connected Twitter account @{platform_username}!', 'success')

    except PlatformAPIError as e:
        logger.warning(f'Twitter API error during OAuth callback for user {current_user.id}: {e.message}')
        flash(f'Twitter API error: {e.message}', 'error')
    except ConfigurationError as e:
        logger.error(f'Configuration error during OAuth callback: {e.message}')
        flash(f'Configuration error: {e.message}', 'error')
    except Exception as e:
        logger.exception(f'Unexpected error during Twitter OAuth callback for user {current_user.id}')
        flash('An unexpected error occurred. Please try again.', 'error')

    return redirect(url_for('social.connections'))


@social_bp.route('/disconnect/twitter', methods=['POST'])
@login_required
def disconnect_twitter():
    """Disconnect Twitter account."""
    service = SocialPostingService()

    if service.disconnect(current_user.id, 'twitter'):
        flash('Twitter account disconnected.', 'success')
    else:
        flash('No Twitter account connected.', 'info')

    return redirect(url_for('social.connections'))


# =============================================================================
# Posting
# =============================================================================

@social_bp.route('/post/<int:snippet_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def post_snippet(snippet_id):
    """Post a snippet to Twitter."""
    service = SocialPostingService()

    try:
        log = service.post_snippet(snippet_id, current_user.id)

        if log.success:
            flash('Posted to Twitter!', 'success')
            if log.platform_post_url:
                flash(f'View tweet: {log.platform_post_url}', 'info')
        else:
            flash(f'Failed to post: {log.error_message}', 'error')

    except SocialPostingError as e:
        logger.warning(f'Social posting error for user {current_user.id}, snippet {snippet_id}: {e.message}')
        flash(f'Error: {e.message}', 'error')
    except Exception as e:
        logger.exception(f'Unexpected error posting snippet {snippet_id} for user {current_user.id}')
        flash('An unexpected error occurred.', 'error')

    # Redirect back to snippet or referrer
    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    return redirect(url_for('atomizer.view_snippet', id=snippet_id))


# =============================================================================
# Post Logs
# =============================================================================

@social_bp.route('/post-logs')
@login_required
def post_logs():
    """View posting history."""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    logs = SocialPostLog.query.filter_by(
        user_id=current_user.id
    ).order_by(
        SocialPostLog.posted_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'social/post_logs.html',
        logs=logs,
    )
