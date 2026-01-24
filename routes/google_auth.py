"""Google OAuth routes for authentication.

Handles:
- /auth/google - Start Google OAuth flow
- /auth/google/callback - Handle OAuth callback
"""
import logging
import secrets
from datetime import datetime, timezone
from flask import Blueprint, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, limiter
from models import User, LoginHistory, AuditLog
from services.google_oauth import (
    is_google_configured,
    get_google_client,
    get_user_info,
)
from routes.auth import is_safe_url

logger = logging.getLogger(__name__)

google_auth_bp = Blueprint('google_auth', __name__)

# Session keys for OAuth flow
SESSION_KEY_GOOGLE_STATE = 'google_oauth_state'
SESSION_KEY_GOOGLE_NONCE = 'google_oauth_nonce'
SESSION_KEY_GOOGLE_NEXT = 'google_oauth_next'


@google_auth_bp.route('/google')
@limiter.limit("10 per minute")
def login():
    """Start Google OAuth 2.0 login flow."""
    # If already authenticated, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if not is_google_configured():
        flash('Google login is not configured.', 'error')
        return redirect(url_for('auth.login'))

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    # Store in session for callback verification
    session[SESSION_KEY_GOOGLE_STATE] = state
    session[SESSION_KEY_GOOGLE_NONCE] = nonce
    session[SESSION_KEY_GOOGLE_NEXT] = request.args.get('next')

    # Get Google OAuth client and redirect to Google
    client = get_google_client()
    redirect_uri = url_for('google_auth.callback', _external=True)

    return client.authorize_redirect(redirect_uri, state=state, nonce=nonce)


@google_auth_bp.route('/google/callback')
@limiter.limit("10 per minute")
def callback():
    """Handle Google OAuth callback."""
    # Check for error from Google
    error = request.args.get('error')
    if error:
        error_desc = request.args.get('error_description', 'Unknown error')
        logger.warning(f'Google OAuth error: {error} - {error_desc}')
        flash(f'Google login failed: {error_desc}', 'error')
        return redirect(url_for('auth.login'))

    # Verify state (CSRF protection)
    state = request.args.get('state')
    expected_state = session.pop(SESSION_KEY_GOOGLE_STATE, None)
    session.pop(SESSION_KEY_GOOGLE_NONCE, None)
    next_page = session.pop(SESSION_KEY_GOOGLE_NEXT, None)

    if not expected_state or state != expected_state:
        logger.warning('Google OAuth state mismatch - possible CSRF attack')
        flash('Invalid state. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    try:
        # Exchange code for token
        client = get_google_client()
        token = client.authorize_access_token()

        # Get user info from ID token
        user_info = get_user_info(token)

        google_id = user_info.get('sub')
        email = user_info.get('email')
        email_verified = user_info.get('email_verified', False)
        name = user_info.get('name')

        if not google_id or not email:
            logger.error('Google OAuth returned incomplete user info')
            flash('Could not retrieve your information from Google.', 'error')
            return redirect(url_for('auth.login'))

        if not email_verified:
            flash('Your Google email is not verified. Please verify it first.', 'error')
            return redirect(url_for('auth.login'))

        # Normalize email
        email = email.strip().lower()

        # Find or create user
        user = _find_or_create_user(google_id, email, name)

        if user is None:
            # Error message already flashed in _find_or_create_user
            return redirect(url_for('auth.login'))

        # Check if user is approved
        if not user.is_approved:
            flash('Your account is pending approval.', 'info')
            return redirect(url_for('auth.pending'))

        # Check if account is locked
        if user.is_locked():
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            remaining = (locked_until - datetime.now(timezone.utc)).total_seconds() // 60
            flash(f'Account locked. Try again in {int(remaining) + 1} minutes.', 'error')
            return redirect(url_for('auth.login'))

        # Successful login - skip local 2FA (Google has its own)
        user.record_successful_login()
        LoginHistory.record(
            user=user,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            success=True
        )

        # Log the OAuth login
        AuditLog.log(
            action=AuditLog.ACTION_GOOGLE_LOGIN,
            actor=user,
            details='Logged in via Google OAuth',
            ip_address=request.remote_addr
        )

        db.session.commit()

        login_user(user, remember=True)  # Google logins get "remember me" by default
        session.permanent = True

        logger.info(f'User {user.email} logged in via Google OAuth')

        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))

    except Exception as e:
        logger.exception('Error during Google OAuth callback')
        flash('An error occurred during Google login. Please try again.', 'error')
        return redirect(url_for('auth.login'))


def _find_or_create_user(google_id, email, name):
    """Find existing user or create new one from Google OAuth.

    Logic:
    1. If user exists with this google_id -> return user
    2. If user exists with this email (no google_id) -> link Google account
    3. If no user exists -> create new user (pending approval)

    Args:
        google_id: Google's unique user ID (sub claim)
        email: User's email from Google
        name: User's display name from Google

    Returns:
        User object or None if error
    """
    try:
        # Case 1: Check if user exists with this Google ID
        user = User.query.filter_by(google_id=google_id).first()
        if user:
            # Update name if user doesn't have one
            if not user.name and name:
                user.name = name
            return user

        # Case 2: Check if user exists with this email
        user = User.query.filter_by(email=email).first()
        if user:
            # Link Google account to existing user
            if user.google_id and user.google_id != google_id:
                # This email is already linked to a different Google account
                # This shouldn't happen normally - log it
                logger.warning(
                    f'Email {email} already linked to different Google ID. '
                    f'Existing: {user.google_id}, New: {google_id}'
                )
                flash('This email is already linked to a different Google account.', 'error')
                return None

            # Link Google to existing account
            user.google_id = google_id
            user.google_linked_at = datetime.now(timezone.utc)
            if not user.name and name:
                user.name = name

            # Mark email as verified (Google verified it)
            if not user.email_verified:
                user.email_verified = True

            db.session.commit()

            AuditLog.log(
                action=AuditLog.ACTION_GOOGLE_ACCOUNT_LINKED,
                actor=user,
                details='Linked Google account to existing local account',
                ip_address=request.remote_addr
            )

            logger.info(f'Linked Google account to existing user: {email}')
            flash('Google account linked to your existing account.', 'success')
            return user

        # Case 3: Create new user
        user = User(
            email=email,
            name=name,
            google_id=google_id,
            google_linked_at=datetime.now(timezone.utc),
            auth_provider='google',
            email_verified=True,  # Google verified the email
            is_approved=False,  # Still requires admin approval
        )
        db.session.add(user)
        db.session.commit()

        AuditLog.log(
            action=AuditLog.ACTION_GOOGLE_SIGNUP,
            target_type='user',
            target_id=user.id,
            target_email=user.email,
            details='New user registered via Google OAuth',
            ip_address=request.remote_addr
        )

        logger.info(f'Created new user via Google OAuth: {email}')
        return user

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception(f'Database error in Google OAuth user handling: {e}')
        flash('A database error occurred. Please try again.', 'error')
        return None
