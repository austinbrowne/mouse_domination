"""Social Posting service for Twitter/X integration.

This service handles:
- Encrypting/decrypting OAuth tokens (Fernet)
- Twitter OAuth 2.0 with PKCE flow
- Posting tweets via Twitter API v2
- Rate limiting and error handling
"""

import os
import time
import json
import secrets
import hashlib
import base64
import requests
from functools import wraps
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

from flask import current_app
from extensions import db
from models import SocialConnection, SocialPostLog, ContentAtomicSnippet


def rate_limit(min_interval=1.0):
    """
    Decorator to enforce minimum interval between API calls.

    Args:
        min_interval: Minimum seconds between calls (default 1s)
    """
    last_call = [0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result
        return wrapper
    return decorator


class SocialPostingError(Exception):
    """Base exception for social posting errors."""

    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(message)


class TokenEncryptionError(SocialPostingError):
    """Encryption/decryption failed."""
    pass


class PlatformAPIError(SocialPostingError):
    """Platform API call failed."""
    pass


class TokenExpiredError(SocialPostingError):
    """OAuth token has expired and needs refresh."""
    pass


class ConfigurationError(SocialPostingError):
    """Missing or invalid configuration."""
    pass


class SocialPostingService:
    """Service for posting to Twitter/X via OAuth 2.0."""

    TWITTER_AUTH_URL = 'https://twitter.com/i/oauth2/authorize'
    TWITTER_TOKEN_URL = 'https://api.twitter.com/2/oauth2/token'
    TWITTER_API_URL = 'https://api.twitter.com/2'

    # Twitter OAuth 2.0 scopes
    TWITTER_SCOPES = ['tweet.read', 'tweet.write', 'users.read', 'offline.access']

    def __init__(self):
        """Initialize the social posting service."""
        self._fernet = None

    @property
    def fernet(self):
        """Lazy-load Fernet cipher for token encryption."""
        if self._fernet is None:
            encryption_key = os.environ.get('SOCIAL_TOKEN_ENCRYPTION_KEY')
            if not encryption_key:
                raise ConfigurationError(
                    'SOCIAL_TOKEN_ENCRYPTION_KEY environment variable not set'
                )
            try:
                from cryptography.fernet import Fernet
                self._fernet = Fernet(encryption_key.encode())
            except Exception as e:
                raise ConfigurationError(f'Invalid encryption key: {e}')
        return self._fernet

    @property
    def twitter_client_id(self):
        """Get Twitter client ID from environment."""
        return os.environ.get('TWITTER_CLIENT_ID')

    @property
    def twitter_client_secret(self):
        """Get Twitter client secret from environment."""
        return os.environ.get('TWITTER_CLIENT_SECRET')

    @property
    def is_twitter_configured(self):
        """Check if Twitter API credentials are configured."""
        return bool(self.twitter_client_id and self.twitter_client_secret)

    # =========================================================================
    # Token Encryption/Decryption
    # =========================================================================

    def encrypt_credentials(self, credentials: dict) -> str:
        """
        Encrypt OAuth credentials for secure storage.

        Args:
            credentials: Dict containing access_token, refresh_token, etc.

        Returns:
            Encrypted string (base64 encoded)
        """
        try:
            json_str = json.dumps(credentials)
            encrypted = self.fernet.encrypt(json_str.encode())
            return encrypted.decode()
        except Exception as e:
            raise TokenEncryptionError(f'Failed to encrypt credentials: {e}')

    def decrypt_credentials(self, encrypted: str) -> dict:
        """
        Decrypt stored OAuth credentials.

        Args:
            encrypted: Encrypted string from database

        Returns:
            Dict containing access_token, refresh_token, etc.
        """
        try:
            decrypted = self.fernet.decrypt(encrypted.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            raise TokenEncryptionError(f'Failed to decrypt credentials: {e}')

    # =========================================================================
    # Twitter OAuth 2.0 with PKCE
    # =========================================================================

    def generate_pkce_pair(self):
        """
        Generate PKCE code_verifier and code_challenge pair.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate random code_verifier (43-128 characters)
        code_verifier = secrets.token_urlsafe(32)

        # Create code_challenge using S256 method
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

        return code_verifier, code_challenge

    def get_twitter_authorize_url(self, redirect_uri: str, state: str, code_challenge: str) -> str:
        """
        Build Twitter OAuth 2.0 authorization URL.

        Args:
            redirect_uri: Callback URL after authorization
            state: Random state for CSRF protection
            code_challenge: PKCE code challenge (S256)

        Returns:
            Full authorization URL to redirect user to
        """
        if not self.is_twitter_configured:
            raise ConfigurationError('Twitter API credentials not configured')

        params = {
            'response_type': 'code',
            'client_id': self.twitter_client_id,
            'redirect_uri': redirect_uri,
            'scope': ' '.join(self.TWITTER_SCOPES),
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }
        return f'{self.TWITTER_AUTH_URL}?{urlencode(params)}'

    @rate_limit(min_interval=1.0)
    def exchange_twitter_code(self, code: str, redirect_uri: str, code_verifier: str) -> dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect_uri used in authorization
            code_verifier: PKCE code verifier

        Returns:
            Dict with access_token, refresh_token, expires_in, etc.
        """
        if not self.is_twitter_configured:
            raise ConfigurationError('Twitter API credentials not configured')

        data = {
            'code': code,
            'grant_type': 'authorization_code',
            'client_id': self.twitter_client_id,
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier,
        }

        # Use Basic auth with client_id:client_secret
        auth = (self.twitter_client_id, self.twitter_client_secret)

        try:
            response = requests.post(
                self.TWITTER_TOKEN_URL,
                data=data,
                auth=auth,
                timeout=30,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                error_data = response.json()
                raise PlatformAPIError(
                    f"Token exchange failed: {error_data.get('error_description', 'Unknown error')}",
                    code='token_exchange_failed'
                )
            elif response.status_code == 401:
                raise PlatformAPIError(
                    'Invalid client credentials',
                    code='invalid_credentials'
                )
            else:
                raise PlatformAPIError(
                    f'Twitter API error: {response.status_code}',
                    code='api_error'
                )

        except requests.Timeout:
            raise PlatformAPIError('Twitter API request timed out', code='timeout')
        except requests.ConnectionError:
            raise PlatformAPIError('Failed to connect to Twitter API', code='connection_error')

    @rate_limit(min_interval=1.0)
    def refresh_twitter_token(self, connection: SocialConnection) -> bool:
        """
        Refresh an expired Twitter access token.

        Args:
            connection: SocialConnection with encrypted credentials

        Returns:
            True if refresh succeeded, False otherwise
        """
        if not self.is_twitter_configured:
            raise ConfigurationError('Twitter API credentials not configured')

        try:
            credentials = self.decrypt_credentials(connection.encrypted_credentials)
        except TokenEncryptionError:
            return False

        refresh_token = credentials.get('refresh_token')
        if not refresh_token:
            return False

        data = {
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'client_id': self.twitter_client_id,
        }

        auth = (self.twitter_client_id, self.twitter_client_secret)

        try:
            response = requests.post(
                self.TWITTER_TOKEN_URL,
                data=data,
                auth=auth,
                timeout=30,
            )

            if response.status_code == 200:
                token_data = response.json()

                # Update stored credentials
                credentials['access_token'] = token_data['access_token']
                if 'refresh_token' in token_data:
                    credentials['refresh_token'] = token_data['refresh_token']

                connection.encrypted_credentials = self.encrypt_credentials(credentials)

                # Update expiry time
                expires_in = token_data.get('expires_in', 7200)
                connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                connection.updated_at = datetime.now(timezone.utc)

                db.session.commit()
                return True
            else:
                current_app.logger.warning(f'Token refresh failed: {response.status_code}')
                return False

        except Exception as e:
            current_app.logger.error(f'Token refresh error: {e}')
            return False

    @rate_limit(min_interval=1.0)
    def get_twitter_user_info(self, access_token: str) -> dict:
        """
        Fetch the authenticated user's Twitter profile.

        Args:
            access_token: Valid access token

        Returns:
            Dict with id, username, name
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(
                f'{self.TWITTER_API_URL}/users/me',
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('data', {})
            elif response.status_code == 401:
                raise TokenExpiredError('Access token expired or invalid')
            else:
                raise PlatformAPIError(
                    f'Failed to fetch user info: {response.status_code}',
                    code='api_error'
                )

        except requests.Timeout:
            raise PlatformAPIError('Twitter API request timed out', code='timeout')
        except requests.ConnectionError:
            raise PlatformAPIError('Failed to connect to Twitter API', code='connection_error')

    # =========================================================================
    # Posting
    # =========================================================================

    @rate_limit(min_interval=1.0)
    def post_to_twitter(self, connection: SocialConnection, content: str, _retry_count: int = 0) -> dict:
        """
        Post a tweet to Twitter/X.

        Args:
            connection: SocialConnection with encrypted credentials
            content: Tweet text (max 280 chars)
            _retry_count: Internal retry counter (do not set manually)

        Returns:
            Dict with success, tweet_id, tweet_url, or error
        """
        MAX_RETRIES = 1  # Only allow one retry after token refresh
        start_time = time.time()

        # Validate content length
        if len(content) > 280:
            return {
                'success': False,
                'error': f'Tweet exceeds 280 characters ({len(content)} chars)',
            }

        # Check if token might be expired
        if connection.token_expires_at and connection.token_expires_at < datetime.now(timezone.utc):
            # Try to refresh
            if not self.refresh_twitter_token(connection):
                return {
                    'success': False,
                    'error': 'Access token expired and refresh failed. Please reconnect your Twitter account.',
                }

        try:
            credentials = self.decrypt_credentials(connection.encrypted_credentials)
        except TokenEncryptionError as e:
            return {
                'success': False,
                'error': str(e),
            }

        access_token = credentials.get('access_token')
        if not access_token:
            return {
                'success': False,
                'error': 'No access token found',
            }

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        payload = {
            'text': content,
        }

        try:
            response = requests.post(
                f'{self.TWITTER_API_URL}/tweets',
                headers=headers,
                json=payload,
                timeout=30,
            )

            response_time = int((time.time() - start_time) * 1000)

            if response.status_code == 201:
                data = response.json()
                tweet_data = data.get('data', {})
                tweet_id = tweet_data.get('id')

                # Build tweet URL
                tweet_url = None
                if tweet_id and connection.platform_username:
                    tweet_url = f'https://twitter.com/{connection.platform_username}/status/{tweet_id}'

                # Update connection last_used
                connection.last_used_at = datetime.now(timezone.utc)
                connection.last_error = None
                db.session.commit()

                return {
                    'success': True,
                    'tweet_id': tweet_id,
                    'tweet_url': tweet_url,
                    'response_time_ms': response_time,
                }

            elif response.status_code == 401:
                # Token expired, try refresh (with retry limit to prevent infinite recursion)
                if _retry_count < MAX_RETRIES and self.refresh_twitter_token(connection):
                    # Retry the post with incremented retry count
                    return self.post_to_twitter(connection, content, _retry_count=_retry_count + 1)
                else:
                    connection.last_error = 'Token expired, refresh failed'
                    db.session.commit()
                    return {
                        'success': False,
                        'error': 'Token expired. Please reconnect your Twitter account.',
                    }

            elif response.status_code == 403:
                error_data = response.json()
                detail = error_data.get('detail', 'Forbidden')
                connection.last_error = detail
                db.session.commit()
                return {
                    'success': False,
                    'error': f'Twitter rejected the request: {detail}',
                }

            elif response.status_code == 429:
                connection.last_error = 'Rate limited'
                db.session.commit()
                return {
                    'success': False,
                    'error': 'Twitter rate limit reached. Please try again later.',
                }

            else:
                error_text = response.text[:200]
                connection.last_error = f'API error {response.status_code}'
                db.session.commit()
                return {
                    'success': False,
                    'error': f'Twitter API error ({response.status_code}): {error_text}',
                }

        except requests.Timeout:
            return {
                'success': False,
                'error': 'Twitter API request timed out',
            }
        except requests.ConnectionError:
            return {
                'success': False,
                'error': 'Failed to connect to Twitter API',
            }
        except Exception as e:
            current_app.logger.error(f'Unexpected error posting to Twitter: {e}')
            return {
                'success': False,
                'error': 'An unexpected error occurred',
            }

    # =========================================================================
    # High-Level Interface
    # =========================================================================

    def post_snippet(self, snippet_id: int, user_id: int) -> SocialPostLog:
        """
        Post a ContentAtomicSnippet to Twitter and log the result.

        Args:
            snippet_id: ID of the snippet to post
            user_id: User ID (for ownership verification)

        Returns:
            SocialPostLog with the result
        """
        # Fetch snippet with ownership check
        snippet = ContentAtomicSnippet.query.filter_by(
            id=snippet_id,
            user_id=user_id
        ).first()

        if not snippet:
            raise SocialPostingError('Snippet not found', code='not_found')

        if snippet.platform != 'twitter':
            raise SocialPostingError(
                f'Snippet is for {snippet.platform}, not Twitter',
                code='wrong_platform'
            )

        # Get user's Twitter connection
        connection = SocialConnection.query.filter_by(
            user_id=user_id,
            platform='twitter',
            is_active=True
        ).first()

        if not connection:
            raise SocialPostingError(
                'No Twitter account connected. Please connect your Twitter account first.',
                code='not_connected'
            )

        # Get content to post
        content = snippet.edited_content or snippet.generated_content

        # Post to Twitter
        result = self.post_to_twitter(connection, content)

        # Create log entry
        log = SocialPostLog(
            user_id=user_id,
            snippet_id=snippet_id,
            connection_id=connection.id,
            platform='twitter',
            content_posted=content,
            success=result.get('success', False),
            platform_post_id=result.get('tweet_id'),
            platform_post_url=result.get('tweet_url'),
            error_message=result.get('error'),
            response_time_ms=result.get('response_time_ms'),
        )
        db.session.add(log)

        # Update snippet if successful
        if result.get('success'):
            snippet.status = 'published'
            snippet.published_date = datetime.now(timezone.utc)
            snippet.published_url = result.get('tweet_url')

        db.session.commit()

        return log

    def get_user_connection(self, user_id: int, platform: str = 'twitter') -> SocialConnection:
        """
        Get a user's social connection for a platform.

        Args:
            user_id: User ID
            platform: Platform name (default 'twitter')

        Returns:
            SocialConnection or None
        """
        return SocialConnection.query.filter_by(
            user_id=user_id,
            platform=platform,
            is_active=True
        ).first()

    def create_connection(
        self,
        user_id: int,
        platform: str,
        platform_user_id: str,
        platform_username: str,
        credentials: dict,
        expires_in: int = None
    ) -> SocialConnection:
        """
        Create or update a social connection for a user.

        Args:
            user_id: User ID
            platform: Platform name
            platform_user_id: Platform's user ID
            platform_username: Platform username/handle
            credentials: OAuth credentials dict
            expires_in: Token expiry in seconds

        Returns:
            SocialConnection
        """
        # Check for existing connection
        connection = SocialConnection.query.filter_by(
            user_id=user_id,
            platform=platform
        ).first()

        encrypted = self.encrypt_credentials(credentials)

        if connection:
            # Update existing
            connection.platform_user_id = platform_user_id
            connection.platform_username = platform_username
            connection.encrypted_credentials = encrypted
            connection.is_active = True
            connection.last_error = None
            connection.updated_at = datetime.now(timezone.utc)
        else:
            # Create new
            connection = SocialConnection(
                user_id=user_id,
                platform=platform,
                platform_user_id=platform_user_id,
                platform_username=platform_username,
                encrypted_credentials=encrypted,
                is_active=True,
            )
            db.session.add(connection)

        # Set token expiry
        if expires_in:
            connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        db.session.commit()
        return connection

    def disconnect(self, user_id: int, platform: str = 'twitter') -> bool:
        """
        Disconnect (deactivate) a social connection.

        Args:
            user_id: User ID
            platform: Platform name

        Returns:
            True if disconnected, False if not found
        """
        connection = SocialConnection.query.filter_by(
            user_id=user_id,
            platform=platform
        ).first()

        if connection:
            connection.is_active = False
            connection.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return True
        return False
