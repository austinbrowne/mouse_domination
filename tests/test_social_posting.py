"""Tests for Social Posting Phase 3: Twitter/X integration.

Tests cover:
- Model operations (SocialConnection, SocialPostLog)
- Service layer (encryption, OAuth flow, posting)
- Routes (connections, OAuth callback, posting)
- Multi-user isolation
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

from app import create_app, db
from models import SocialConnection, SocialPostLog, ContentAtomicSnippet, User
from config import TestConfig


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def test_user(app):
    """Create an approved test user."""
    with app.app_context():
        user = User(
            email='social_test@example.com',
            name='Social Test User',
            is_approved=True,
            is_admin=False
        )
        user.set_password('TestPassword123!')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {'id': user_id, 'email': 'social_test@example.com', 'password': 'TestPassword123!'}


@pytest.fixture
def other_user(app):
    """Create another user for isolation tests."""
    with app.app_context():
        user = User(
            email='other@example.com',
            name='Other User',
            is_approved=True,
            is_admin=False
        )
        user.set_password('OtherPassword123!')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {'id': user_id, 'email': 'other@example.com', 'password': 'OtherPassword123!'}


@pytest.fixture
def auth_client(app, test_user):
    """Create authenticated test client."""
    client = app.test_client()
    client.post('/auth/login', data={
        'email': test_user['email'],
        'password': test_user['password']
    })
    return client


@pytest.fixture
def twitter_connection(app, test_user):
    """Create a Twitter connection for the test user."""
    with app.app_context():
        # Create a mock encrypted credentials blob
        mock_credentials = json.dumps({
            'access_token': 'mock_access_token',
            'refresh_token': 'mock_refresh_token',
        })

        connection = SocialConnection(
            user_id=test_user['id'],
            platform='twitter',
            platform_user_id='12345',
            platform_username='testuser',
            encrypted_credentials=mock_credentials,  # Not actually encrypted for tests
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            is_active=True,
        )
        db.session.add(connection)
        db.session.commit()
        connection_id = connection.id

    return {'id': connection_id, 'user_id': test_user['id'], 'username': 'testuser'}


@pytest.fixture
def twitter_snippet(app, test_user):
    """Create a Twitter snippet for testing."""
    with app.app_context():
        snippet = ContentAtomicSnippet(
            user_id=test_user['id'],
            platform='twitter',
            source_type='manual',
            source_content='This is source content for testing.',
            generated_content='This is a test tweet! #testing',
            character_count=32,
            word_count=6,
            status='approved',
        )
        db.session.add(snippet)
        db.session.commit()
        snippet_id = snippet.id

    return {'id': snippet_id, 'user_id': test_user['id']}


# =============================================================================
# Model Tests
# =============================================================================

class TestSocialConnectionModel:
    """Tests for SocialConnection model."""

    def test_create_connection(self, app, test_user):
        """Test creating a social connection."""
        with app.app_context():
            connection = SocialConnection(
                user_id=test_user['id'],
                platform='twitter',
                platform_user_id='12345',
                platform_username='testhandle',
                encrypted_credentials='encrypted_blob',
                is_active=True,
            )
            db.session.add(connection)
            db.session.commit()

            assert connection.id is not None
            assert connection.platform == 'twitter'
            assert connection.platform_username == 'testhandle'
            assert connection.is_active is True

    def test_unique_user_platform_constraint(self, app, test_user):
        """Test that user can only have one connection per platform."""
        with app.app_context():
            connection1 = SocialConnection(
                user_id=test_user['id'],
                platform='twitter',
                encrypted_credentials='creds1',
            )
            db.session.add(connection1)
            db.session.commit()

            # Try to add another Twitter connection for same user
            connection2 = SocialConnection(
                user_id=test_user['id'],
                platform='twitter',
                encrypted_credentials='creds2',
            )
            db.session.add(connection2)

            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()

    def test_get_platform_display(self, app):
        """Test platform display name method."""
        with app.app_context():
            assert SocialConnection.get_platform_display('twitter') == 'Twitter/X'
            assert SocialConnection.get_platform_display('unknown') == 'Unknown'

    def test_to_dict(self, app, test_user):
        """Test model to_dict serialization."""
        with app.app_context():
            connection = SocialConnection(
                user_id=test_user['id'],
                platform='twitter',
                platform_user_id='12345',
                platform_username='testhandle',
                encrypted_credentials='encrypted',
                is_active=True,
            )
            db.session.add(connection)
            db.session.commit()

            data = connection.to_dict()
            assert data['platform'] == 'twitter'
            assert data['platform_display'] == 'Twitter/X'
            assert data['platform_username'] == 'testhandle'
            assert data['is_active'] is True
            # Should not expose credentials
            assert 'encrypted_credentials' not in data


class TestSocialPostLogModel:
    """Tests for SocialPostLog model."""

    def test_create_post_log(self, app, test_user, twitter_connection, twitter_snippet):
        """Test creating a post log entry."""
        with app.app_context():
            log = SocialPostLog(
                user_id=test_user['id'],
                snippet_id=twitter_snippet['id'],
                connection_id=twitter_connection['id'],
                platform='twitter',
                content_posted='Test tweet content',
                success=True,
                platform_post_id='1234567890',
                platform_post_url='https://twitter.com/testuser/status/1234567890',
                response_time_ms=150,
            )
            db.session.add(log)
            db.session.commit()

            assert log.id is not None
            assert log.success is True
            assert log.platform_post_id == '1234567890'

    def test_failed_post_log(self, app, test_user):
        """Test logging a failed post."""
        with app.app_context():
            log = SocialPostLog(
                user_id=test_user['id'],
                platform='twitter',
                content_posted='Failed tweet',
                success=False,
                error_message='Rate limit exceeded',
            )
            db.session.add(log)
            db.session.commit()

            assert log.success is False
            assert log.error_message == 'Rate limit exceeded'
            assert log.platform_post_url is None


# =============================================================================
# Service Tests
# =============================================================================

class TestSocialPostingService:
    """Tests for SocialPostingService."""

    def test_encryption_key_required(self, app):
        """Test that service requires encryption key."""
        with app.app_context():
            from services.social_posting import SocialPostingService, ConfigurationError

            # Ensure env var is not set
            with patch.dict('os.environ', {}, clear=True):
                service = SocialPostingService()
                with pytest.raises(ConfigurationError):
                    _ = service.fernet

    @patch.dict('os.environ', {'SOCIAL_TOKEN_ENCRYPTION_KEY': 'Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MDEyMzQ1Njc4OTAx'})
    def test_encrypt_decrypt_credentials(self, app):
        """Test credential encryption and decryption."""
        with app.app_context():
            # Use a valid Fernet key for testing
            from cryptography.fernet import Fernet
            test_key = Fernet.generate_key().decode()

            with patch.dict('os.environ', {'SOCIAL_TOKEN_ENCRYPTION_KEY': test_key}):
                from services.social_posting import SocialPostingService

                service = SocialPostingService()
                credentials = {
                    'access_token': 'test_access_token',
                    'refresh_token': 'test_refresh_token',
                }

                encrypted = service.encrypt_credentials(credentials)
                assert encrypted != json.dumps(credentials)  # Should be encrypted

                decrypted = service.decrypt_credentials(encrypted)
                assert decrypted == credentials

    def test_generate_pkce_pair(self, app):
        """Test PKCE code verifier and challenge generation."""
        with app.app_context():
            from services.social_posting import SocialPostingService

            service = SocialPostingService()
            verifier, challenge = service.generate_pkce_pair()

            # Verifier should be 43 characters (base64url of 32 bytes)
            assert len(verifier) == 43
            # Challenge should be 43 characters (base64url of SHA256)
            assert len(challenge) == 43
            # They should be different
            assert verifier != challenge

    @patch.dict('os.environ', {
        'TWITTER_CLIENT_ID': 'test_client_id',
        'TWITTER_CLIENT_SECRET': 'test_client_secret',
    })
    def test_twitter_configured(self, app):
        """Test Twitter configuration check."""
        with app.app_context():
            from services.social_posting import SocialPostingService

            service = SocialPostingService()
            assert service.is_twitter_configured is True

    def test_twitter_not_configured(self, app):
        """Test Twitter configuration check when not set."""
        with app.app_context():
            with patch.dict('os.environ', {}, clear=True):
                from services.social_posting import SocialPostingService

                service = SocialPostingService()
                assert service.is_twitter_configured is False

    def test_post_to_twitter_retry_limit_prevents_infinite_recursion(self, app, test_user):
        """Test that post_to_twitter has retry limit to prevent infinite recursion on 401."""
        with app.app_context():
            from cryptography.fernet import Fernet
            test_key = Fernet.generate_key().decode()

            with patch.dict('os.environ', {'SOCIAL_TOKEN_ENCRYPTION_KEY': test_key}):
                from services.social_posting import SocialPostingService

                service = SocialPostingService()

                # Create a connection with valid encrypted credentials
                credentials = {
                    'access_token': 'test_access_token',
                    'refresh_token': 'test_refresh_token',
                }

                connection = SocialConnection(
                    user_id=test_user['id'],
                    platform='twitter',
                    platform_user_id='12345',
                    platform_username='testuser',
                    encrypted_credentials=service.encrypt_credentials(credentials),
                    token_expires_at=None,  # Skip expiry check, let 401 trigger refresh
                    is_active=True,
                )
                db.session.add(connection)
                db.session.commit()

                # Mock requests.post to always return 401 (even after refresh)
                mock_response = Mock()
                mock_response.status_code = 401

                with patch('services.social_posting.requests.post', return_value=mock_response):
                    # Mock refresh_twitter_token to always succeed (simulating a token that
                    # refreshes but still gets 401 - edge case that could cause infinite loop)
                    with patch.object(service, 'refresh_twitter_token', return_value=True) as mock_refresh:
                        result = service.post_to_twitter(connection, 'Test tweet')

                        # Should have tried refresh only once (MAX_RETRIES = 1)
                        assert mock_refresh.call_count == 1

                        # Should return failure, not loop forever
                        assert result['success'] is False
                        assert 'expired' in result['error'].lower() or 'reconnect' in result['error'].lower()


# =============================================================================
# Route Tests
# =============================================================================

class TestConnectionRoutes:
    """Tests for social connection routes."""

    def test_connections_page_requires_login(self, app):
        """Test connections page requires authentication."""
        client = app.test_client()
        response = client.get('/social/connections')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_connections_page_loads(self, auth_client, app):
        """Test connections page loads for authenticated user."""
        with app.app_context():
            response = auth_client.get('/social/connections')
            assert response.status_code == 200
            assert b'Social Connections' in response.data

    def test_connect_twitter_not_configured(self, auth_client, app):
        """Test connecting Twitter when not configured."""
        with app.app_context():
            with patch.dict('os.environ', {}, clear=True):
                response = auth_client.get('/social/connect/twitter')
                # Should redirect with error
                assert response.status_code == 302

    def test_disconnect_twitter(self, auth_client, app, twitter_connection):
        """Test disconnecting Twitter."""
        with app.app_context():
            response = auth_client.post('/social/disconnect/twitter')
            assert response.status_code == 302

            # Verify connection is deactivated
            connection = SocialConnection.query.get(twitter_connection['id'])
            assert connection.is_active is False


class TestPostingRoutes:
    """Tests for social posting routes."""

    def test_post_snippet_requires_login(self, app, twitter_snippet):
        """Test posting requires authentication."""
        client = app.test_client()
        response = client.post(f'/social/post/{twitter_snippet["id"]}')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_post_snippet_no_connection(self, auth_client, app, twitter_snippet):
        """Test posting without Twitter connection."""
        with app.app_context():
            response = auth_client.post(f'/social/post/{twitter_snippet["id"]}')
            # Should redirect with error about no connection
            assert response.status_code == 302

    def test_post_logs_page(self, auth_client, app):
        """Test post logs page loads."""
        with app.app_context():
            response = auth_client.get('/social/post-logs')
            assert response.status_code == 200
            assert b'Post History' in response.data


# =============================================================================
# Multi-User Isolation Tests
# =============================================================================

class TestMultiUserIsolation:
    """Tests for multi-user data isolation."""

    def test_users_cannot_see_other_connections(self, app, test_user, other_user, twitter_connection):
        """Test users can only see their own connections."""
        # Login as other user
        client = app.test_client()
        client.post('/auth/login', data={
            'email': other_user['email'],
            'password': 'OtherPassword123!'
        })

        with app.app_context():
            response = client.get('/social/connections')
            # Should not see test_user's Twitter connection
            assert b'testuser' not in response.data

    def test_users_cannot_post_other_snippets(self, app, test_user, other_user, twitter_snippet):
        """Test users cannot post other users' snippets."""
        # Login as other user
        client = app.test_client()
        client.post('/auth/login', data={
            'email': other_user['email'],
            'password': 'OtherPassword123!'
        })

        with app.app_context():
            response = client.post(f'/social/post/{twitter_snippet["id"]}')
            # Should fail since snippet belongs to test_user
            assert response.status_code == 302  # Redirect with error

    def test_users_cannot_disconnect_other_connections(self, app, test_user, other_user, twitter_connection):
        """Test users cannot disconnect other users' connections."""
        # Login as other user
        client = app.test_client()
        client.post('/auth/login', data={
            'email': other_user['email'],
            'password': 'OtherPassword123!'
        })

        with app.app_context():
            response = client.post('/social/disconnect/twitter')
            # Should not affect test_user's connection
            connection = SocialConnection.query.get(twitter_connection['id'])
            assert connection.is_active is True  # Still active


# =============================================================================
# OAuth Flow Tests
# =============================================================================

class TestOAuthFlow:
    """Tests for OAuth callback handling."""

    @patch.dict('os.environ', {
        'TWITTER_CLIENT_ID': 'test_client_id',
        'TWITTER_CLIENT_SECRET': 'test_client_secret',
    })
    def test_callback_validates_state(self, auth_client, app):
        """Test OAuth callback validates state parameter."""
        with app.app_context():
            # Call callback without setting up session state
            response = auth_client.get('/social/callback/twitter?code=test_code&state=invalid_state')
            assert response.status_code == 302
            # Should redirect with error about invalid state

    def test_callback_handles_error(self, auth_client, app):
        """Test OAuth callback handles authorization errors."""
        with app.app_context():
            response = auth_client.get('/social/callback/twitter?error=access_denied&error_description=User%20denied%20access')
            assert response.status_code == 302
            # Should redirect with error message
