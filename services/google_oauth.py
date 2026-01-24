"""Google OAuth 2.0 service using Authlib.

Handles:
- OAuth client initialization
- Authorization URL generation
- Token exchange
- User info retrieval
"""
import logging
from flask import current_app
from authlib.integrations.flask_client import OAuth

logger = logging.getLogger(__name__)

# Global OAuth registry - initialized once per app
oauth = OAuth()


def init_google_oauth(app):
    """Initialize Google OAuth client with Flask app.

    Call this from create_app() after app is created.
    """
    oauth.init_app(app)

    # Only register if credentials are configured
    if app.config.get('GOOGLE_CLIENT_ID') and app.config.get('GOOGLE_CLIENT_SECRET'):
        oauth.register(
            name='google',
            client_id=app.config['GOOGLE_CLIENT_ID'],
            client_secret=app.config['GOOGLE_CLIENT_SECRET'],
            server_metadata_url=app.config.get(
                'GOOGLE_DISCOVERY_URL',
                'https://accounts.google.com/.well-known/openid-configuration'
            ),
            client_kwargs={
                'scope': 'openid email profile',
            },
        )
        logger.info('Google OAuth client initialized')
    else:
        logger.warning('Google OAuth not configured - GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET missing')


def is_google_configured():
    """Check if Google OAuth is properly configured."""
    return bool(
        current_app.config.get('GOOGLE_CLIENT_ID') and
        current_app.config.get('GOOGLE_CLIENT_SECRET')
    )


def get_google_client():
    """Get the Google OAuth client.

    Returns:
        OAuth client or None if not configured
    """
    if not is_google_configured():
        return None
    return oauth.google


def get_user_info(token):
    """Fetch user info from Google.

    Args:
        token: Access token dict from authorize_access_token()

    Returns:
        Dict with user info: sub (Google ID), email, email_verified, name, picture
    """
    # Parse the id_token to get user info (OpenID Connect)
    # This is more secure than calling userinfo endpoint
    userinfo = token.get('userinfo')
    if userinfo:
        return userinfo

    # Fallback: fetch from userinfo endpoint
    client = get_google_client()
    if not client:
        raise RuntimeError('Google OAuth not configured')

    resp = client.get('https://openidconnect.googleapis.com/v1/userinfo')
    return resp.json()
