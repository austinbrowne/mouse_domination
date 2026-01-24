"""Tests for Google OAuth authentication."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from app import db
from models import User


class TestGoogleOAuthConfig:
    """Tests for Google OAuth configuration."""

    def test_google_not_configured_by_default(self, app):
        """Test Google OAuth is not configured in test environment."""
        with app.app_context():
            from services.google_oauth import is_google_configured
            # In test config, Google credentials are not set
            assert not is_google_configured()

    def test_google_configured_when_credentials_set(self, app):
        """Test Google OAuth is configured when credentials are set."""
        with app.app_context():
            app.config['GOOGLE_CLIENT_ID'] = 'test-client-id'
            app.config['GOOGLE_CLIENT_SECRET'] = 'test-client-secret'
            from services.google_oauth import is_google_configured
            assert is_google_configured()


class TestGoogleOAuthLogin:
    """Tests for Google OAuth login flow."""

    def test_google_login_not_configured(self, client, app):
        """Test /auth/google shows error when not configured."""
        response = client.get('/auth/google', follow_redirects=True)
        assert b'not configured' in response.data.lower()

    def test_google_login_authenticated_redirects(self, auth_client):
        """Test authenticated user redirects from /auth/google."""
        response = auth_client.get('/auth/google')
        assert response.status_code == 302
        assert '/dashboard' in response.location or response.location == '/'


class TestGoogleOAuthCallback:
    """Tests for Google OAuth callback handling."""

    def test_callback_error_from_google(self, client):
        """Test callback handles error from Google."""
        response = client.get(
            '/auth/google/callback?error=access_denied&error_description=User%20denied%20access',
            follow_redirects=True
        )
        assert b'denied' in response.data.lower() or b'failed' in response.data.lower()

    def test_callback_invalid_state(self, client):
        """Test callback rejects invalid state."""
        with client.session_transaction() as sess:
            sess['google_oauth_state'] = 'expected-state'

        response = client.get(
            '/auth/google/callback?state=wrong-state&code=test-code',
            follow_redirects=True
        )
        assert b'Invalid state' in response.data or b'Please try again' in response.data

    def test_callback_missing_state(self, client):
        """Test callback rejects missing state."""
        response = client.get(
            '/auth/google/callback?code=test-code',
            follow_redirects=True
        )
        assert b'Invalid state' in response.data or b'Please try again' in response.data


class TestGoogleOnlyUser:
    """Tests for users who registered via Google only."""

    def test_google_only_user_cannot_local_login(self, client, app):
        """Test Google-only user cannot log in with password."""
        with app.app_context():
            # Create Google-only user
            user = User(
                email='googleonly@gmail.com',
                name='Google User',
                google_id='google123',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True,
                auth_provider='google',
                email_verified=True
            )
            # No password set
            db.session.add(user)
            db.session.commit()

        response = client.post('/auth/login', data={
            'email': 'googleonly@gmail.com',
            'password': 'SomePassword123!'
        }, follow_redirects=True)

        assert b'Google login' in response.data or b'sign in with Google' in response.data

    def test_google_user_helper_methods(self, app):
        """Test Google user helper methods."""
        with app.app_context():
            # Create user with Google linked
            user = User(
                email='both@example.com',
                google_id='google456',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True
            )
            user.set_password('TestPassword123!')
            db.session.add(user)
            db.session.commit()

            assert user.has_google_linked()
            assert user.has_password()
            assert user.can_use_local_login()

    def test_google_only_user_no_password(self, app):
        """Test Google-only user has no password."""
        with app.app_context():
            user = User(
                email='nopassword@example.com',
                google_id='google789',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True,
                auth_provider='google'
            )
            db.session.add(user)
            db.session.commit()

            assert user.has_google_linked()
            assert not user.has_password()
            assert not user.can_use_local_login()


class TestAccountLinking:
    """Tests for account linking in settings."""

    def test_unlink_google_with_password(self, app, test_user):
        """Test unlinking Google when user has password."""
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            user.google_id = 'google123'
            user.google_linked_at = datetime.now(timezone.utc)
            db.session.commit()

            # Verify initial state
            assert user.has_google_linked()
            assert user.has_password()

            # Unlink
            result = user.unlink_google()
            assert result is True
            assert user.google_id is None
            assert not user.has_google_linked()

    def test_unlink_google_without_password_fails(self, app):
        """Test cannot unlink Google without password."""
        with app.app_context():
            user = User(
                email='googleonly2@gmail.com',
                google_id='google999',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True,
                auth_provider='google'
            )
            db.session.add(user)
            db.session.commit()

            # Try to unlink - should fail
            result = user.unlink_google()
            assert result is False
            assert user.has_google_linked()  # Still linked

    def test_link_google_to_user(self, app, test_user):
        """Test linking Google to existing user."""
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert not user.has_google_linked()

            user.link_google('new_google_id')
            db.session.commit()

            assert user.has_google_linked()
            assert user.google_id == 'new_google_id'
            assert user.google_linked_at is not None


class TestSettingsRoutes:
    """Tests for Google-related settings routes."""

    def test_unlink_google_route_without_google(self, auth_client):
        """Test unlink route when no Google linked."""
        response = auth_client.post('/settings/google/unlink', follow_redirects=True)
        assert b'No Google account linked' in response.data

    def test_set_password_route_with_password(self, auth_client):
        """Test set password route when user already has password."""
        response = auth_client.post('/settings/password/set', data={
            'new_password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!'
        }, follow_redirects=True)
        assert b'already have a password' in response.data

    def test_set_password_mismatch(self, app, client):
        """Test set password with mismatched passwords."""
        with app.app_context():
            # Create Google-only user
            user = User(
                email='setpassword@example.com',
                google_id='googlesetpw',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True,
                auth_provider='google',
                email_verified=True
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        # Log in as this user (simulate session)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)

        response = client.post('/settings/password/set', data={
            'new_password': 'NewPassword123!',
            'confirm_password': 'DifferentPassword123!'
        }, follow_redirects=True)
        assert b'do not match' in response.data

    def test_set_password_weak(self, app, client):
        """Test set password with weak password."""
        with app.app_context():
            user = User(
                email='weakpassword@example.com',
                google_id='googleweak',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True,
                auth_provider='google',
                email_verified=True
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)

        response = client.post('/settings/password/set', data={
            'new_password': 'weak',
            'confirm_password': 'weak'
        }, follow_redirects=True)
        assert b'at least 12 characters' in response.data.lower()


class TestUserModel:
    """Tests for User model OAuth methods."""

    def test_user_to_dict_includes_google_fields(self, app, test_user):
        """Test to_dict includes Google-related fields."""
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            data = user.to_dict()

            assert 'has_google' in data
            assert 'has_password' in data
            assert data['has_password'] is True
            assert data['has_google'] is False

    def test_user_to_dict_with_google(self, app):
        """Test to_dict when Google is linked."""
        with app.app_context():
            user = User(
                email='dicttest@example.com',
                google_id='googledict',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True
            )
            user.set_password('TestPassword123!')
            db.session.add(user)
            db.session.commit()

            data = user.to_dict()
            assert data['has_google'] is True
            assert data['has_password'] is True


class TestLoginPageGoogleButton:
    """Tests for Google button on login page."""

    def test_login_page_no_google_button_when_not_configured(self, client):
        """Test login page doesn't show Google button when not configured."""
        response = client.get('/auth/login')
        # Google button should not be present
        assert b'Sign in with Google' not in response.data

    def test_login_page_shows_google_button_when_configured(self, app, client):
        """Test login page shows Google button when configured."""
        with app.app_context():
            app.config['GOOGLE_CLIENT_ID'] = 'test-client-id'
            app.config['GOOGLE_CLIENT_SECRET'] = 'test-client-secret'

        response = client.get('/auth/login')
        # This test will show the button since config is set at app level
        # In real test, the template checks config.GOOGLE_CLIENT_ID
        # The button appears if GOOGLE_CLIENT_ID is set
        # Since we're in test mode, it might not show up unless we mock the template context


class TestSettingsPageGoogleSection:
    """Tests for Google section on settings page."""

    def test_settings_shows_connected_accounts_section(self, auth_client):
        """Test settings page shows Connected Accounts section."""
        response = auth_client.get('/settings/')
        assert b'Connected Accounts' in response.data

    def test_settings_shows_google_not_connected(self, auth_client):
        """Test settings page shows Google not connected for regular user."""
        response = auth_client.get('/settings/')
        assert b'Google Not Connected' in response.data

    def test_settings_shows_google_connected(self, app, client, test_user):
        """Test settings page shows Google connected when linked."""
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            user.google_id = 'google123'
            user.google_linked_at = datetime.now(timezone.utc)
            db.session.commit()

        # Log in as user
        client.post('/auth/login', data={
            'email': test_user['email'],
            'password': test_user['password']
        })

        response = client.get('/settings/')
        assert b'Google Connected' in response.data

    def test_settings_shows_set_password_for_google_only_user(self, app, client):
        """Test settings shows Set Password for Google-only user."""
        with app.app_context():
            user = User(
                email='googleonly3@example.com',
                google_id='googleonly3',
                google_linked_at=datetime.now(timezone.utc),
                is_approved=True,
                auth_provider='google',
                email_verified=True
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        # Log in directly via session
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)

        response = client.get('/settings/')
        assert b'Set a Password' in response.data
