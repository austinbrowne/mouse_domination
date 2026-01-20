"""Comprehensive tests for Settings functionality.

Test Categories:
A. Authentication Requirements
B. Profile Update
C. Password Change
D. 2FA Setup Flow
E. 2FA Verification
F. Recovery Codes
G. 2FA Disable
H. Multi-User Isolation
"""
import pytest
from unittest.mock import patch, MagicMock
from models import User
from extensions import db


# ============================================================================
# A. Authentication Requirements
# ============================================================================

class TestSettingsAuth:
    """Tests for authentication requirements."""

    def test_settings_index_requires_auth(self, client):
        """Test settings page requires authentication."""
        response = client.get('/settings/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_settings_profile_requires_auth(self, client):
        """Test profile update requires authentication."""
        response = client.post('/settings/profile', data={'name': 'Test'})
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_settings_password_requires_auth(self, client):
        """Test password change requires authentication."""
        response = client.post('/settings/password', data={
            'current_password': 'test',
            'new_password': 'test',
            'confirm_password': 'test'
        })
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_settings_2fa_setup_requires_auth(self, client):
        """Test 2FA setup requires authentication."""
        response = client.get('/settings/2fa/setup')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_settings_2fa_verify_requires_auth(self, client):
        """Test 2FA verify requires authentication."""
        response = client.post('/settings/2fa/verify', data={'code': '123456'})
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_settings_2fa_disable_requires_auth(self, client):
        """Test 2FA disable requires authentication."""
        response = client.post('/settings/2fa/disable', data={'password': 'test'})
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_settings_recovery_codes_requires_auth(self, client):
        """Test recovery codes page requires authentication."""
        response = client.get('/settings/2fa/recovery-codes')
        assert response.status_code == 302
        assert '/auth/login' in response.location


# ============================================================================
# B. Settings Index Page
# ============================================================================

class TestSettingsIndex:
    """Tests for settings index page."""

    def test_settings_index_renders(self, auth_client):
        """Test settings page renders for authenticated user."""
        response = auth_client.get('/settings/')
        assert response.status_code == 200
        assert b'Account Settings' in response.data

    def test_settings_shows_user_email(self, auth_client, test_user):
        """Test settings page shows user email."""
        response = auth_client.get('/settings/')
        assert response.status_code == 200
        assert test_user['email'].encode() in response.data

    def test_settings_shows_login_history(self, auth_client):
        """Test settings page shows login history section."""
        response = auth_client.get('/settings/')
        assert response.status_code == 200
        assert b'Login' in response.data or b'login' in response.data


# ============================================================================
# C. Profile Update
# ============================================================================

class TestProfileUpdate:
    """Tests for profile update functionality."""

    def test_update_profile_success(self, auth_client, app, test_user):
        """Test updating profile name."""
        response = auth_client.post('/settings/profile', data={
            'name': 'New Name'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Profile updated' in response.data or b'updated successfully' in response.data.lower()

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.name == 'New Name'

    def test_update_profile_empty_name(self, auth_client, app, test_user):
        """Test clearing profile name."""
        # First set a name
        auth_client.post('/settings/profile', data={'name': 'Initial Name'})

        # Then clear it
        response = auth_client.post('/settings/profile', data={
            'name': ''
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.name is None

    def test_update_profile_name_too_long(self, auth_client):
        """Test profile name length validation."""
        long_name = 'A' * 101  # More than 100 chars

        response = auth_client.post('/settings/profile', data={
            'name': long_name
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'100 characters' in response.data

    def test_update_profile_strips_whitespace(self, auth_client, app, test_user):
        """Test profile name whitespace is stripped."""
        response = auth_client.post('/settings/profile', data={
            'name': '  Padded Name  '
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.name == 'Padded Name'


# ============================================================================
# D. Password Change
# ============================================================================

class TestPasswordChange:
    """Tests for password change functionality."""

    def test_change_password_success(self, auth_client, app, test_user):
        """Test successful password change."""
        new_password = 'NewSecureP@ss123!'

        response = auth_client.post('/settings/password', data={
            'current_password': test_user['password'],
            'new_password': new_password,
            'confirm_password': new_password
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Password changed' in response.data or b'changed successfully' in response.data.lower()

        # Verify new password works
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.check_password(new_password)

    def test_change_password_wrong_current(self, auth_client):
        """Test password change with wrong current password."""
        response = auth_client.post('/settings/password', data={
            'current_password': 'WrongPassword123!',
            'new_password': 'NewSecureP@ss123!',
            'confirm_password': 'NewSecureP@ss123!'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'incorrect' in response.data.lower()

    def test_change_password_mismatch(self, auth_client, test_user):
        """Test password change with mismatched confirmation."""
        response = auth_client.post('/settings/password', data={
            'current_password': test_user['password'],
            'new_password': 'NewSecureP@ss123!',
            'confirm_password': 'DifferentP@ss123!'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'do not match' in response.data.lower()

    def test_change_password_weak_password(self, auth_client, test_user):
        """Test password change with weak password."""
        response = auth_client.post('/settings/password', data={
            'current_password': test_user['password'],
            'new_password': 'weak',
            'confirm_password': 'weak'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should show password requirements error

    def test_change_password_same_as_current(self, auth_client, test_user):
        """Test password change to same password."""
        response = auth_client.post('/settings/password', data={
            'current_password': test_user['password'],
            'new_password': test_user['password'],
            'confirm_password': test_user['password']
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'different' in response.data.lower()


# ============================================================================
# E. 2FA Setup Flow
# ============================================================================

class Test2FASetup:
    """Tests for 2FA setup flow."""

    def test_2fa_setup_page_renders(self, auth_client):
        """Test 2FA setup page renders."""
        response = auth_client.get('/settings/2fa/setup')
        assert response.status_code == 200
        assert b'Two-Factor' in response.data or b'2FA' in response.data

    def test_2fa_setup_shows_qr_code(self, auth_client):
        """Test 2FA setup shows QR code."""
        response = auth_client.get('/settings/2fa/setup')
        assert response.status_code == 200
        # QR code is embedded as base64 image
        assert b'data:image/png;base64' in response.data

    def test_2fa_setup_shows_secret(self, auth_client, app, test_user):
        """Test 2FA setup shows secret for manual entry."""
        response = auth_client.get('/settings/2fa/setup')
        assert response.status_code == 200

        # Should have generated a TOTP secret
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.totp_secret is not None
            # Secret should appear on page for manual entry
            assert user.totp_secret.encode() in response.data

    def test_2fa_setup_post_regenerates_secret(self, auth_client, app, test_user):
        """Test POST to 2FA setup regenerates the secret."""
        # First GET to generate initial secret
        auth_client.get('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            old_secret = user.totp_secret

        # POST to regenerate
        response = auth_client.post('/settings/2fa/setup')
        assert response.status_code == 200

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            # Secret should be different
            assert user.totp_secret != old_secret

    def test_2fa_setup_redirect_if_already_enabled(self, app, test_user):
        """Test 2FA setup redirects if already enabled."""
        # Enable 2FA first
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            user.generate_totp_secret()
            user.totp_enabled = True
            db.session.commit()

        # Create fresh client AFTER enabling 2FA (important for session state)
        client = app.test_client()
        client.post('/auth/login', data={
            'email': test_user['email'],
            'password': test_user['password']
        })

        response = client.get('/settings/2fa/setup')
        assert response.status_code == 302
        assert 'settings' in response.location


# ============================================================================
# F. 2FA Verification
# ============================================================================

class Test2FAVerification:
    """Tests for 2FA verification."""

    def test_2fa_verify_invalid_code_format(self, auth_client):
        """Test 2FA verify with invalid code format."""
        # First setup 2FA
        auth_client.get('/settings/2fa/setup')

        response = auth_client.post('/settings/2fa/verify', data={
            'code': 'abc123'  # Non-numeric
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'valid 6-digit' in response.data.lower()

    def test_2fa_verify_short_code(self, auth_client):
        """Test 2FA verify with too short code."""
        auth_client.get('/settings/2fa/setup')

        response = auth_client.post('/settings/2fa/verify', data={
            'code': '123'  # Too short
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'valid 6-digit' in response.data.lower()

    def test_2fa_verify_wrong_code(self, auth_client, app, test_user):
        """Test 2FA verify with wrong code."""
        auth_client.get('/settings/2fa/setup')

        response = auth_client.post('/settings/2fa/verify', data={
            'code': '000000'  # Unlikely to be valid
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Invalid code' in response.data or b'try again' in response.data.lower()

        # 2FA should not be enabled
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.totp_enabled is False

    def test_2fa_verify_with_valid_code(self, auth_client, app, test_user):
        """Test 2FA verify with valid code."""
        # Setup 2FA
        auth_client.get('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            # Generate a valid code
            import pyotp
            totp = pyotp.TOTP(user.totp_secret)
            valid_code = totp.now()

        response = auth_client.post('/settings/2fa/verify', data={
            'code': valid_code
        }, follow_redirects=False)

        # Should redirect to recovery codes page
        assert response.status_code == 302
        assert 'recovery-codes' in response.location

        # 2FA should be enabled
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.totp_enabled is True

    def test_2fa_verify_code_with_spaces(self, auth_client, app, test_user):
        """Test 2FA verify handles spaces in code."""
        auth_client.get('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            import pyotp
            totp = pyotp.TOTP(user.totp_secret)
            valid_code = totp.now()

        # Add spaces to code
        spaced_code = f'{valid_code[:3]} {valid_code[3:]}'

        response = auth_client.post('/settings/2fa/verify', data={
            'code': spaced_code
        }, follow_redirects=False)

        # Should still work
        assert response.status_code == 302
        assert 'recovery-codes' in response.location


# ============================================================================
# G. Recovery Codes
# ============================================================================

class TestRecoveryCodes:
    """Tests for recovery codes functionality."""

    def test_recovery_codes_shown_after_2fa_setup(self, auth_client, app, test_user):
        """Test recovery codes are shown after 2FA setup."""
        # Setup and verify 2FA
        auth_client.get('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            import pyotp
            totp = pyotp.TOTP(user.totp_secret)
            valid_code = totp.now()

        auth_client.post('/settings/2fa/verify', data={'code': valid_code})

        # Follow redirect to recovery codes
        response = auth_client.get('/settings/2fa/recovery-codes')
        assert response.status_code == 200
        # Should show recovery codes
        assert b'recovery' in response.data.lower()

    def test_recovery_codes_only_shown_once(self, auth_client, app, test_user):
        """Test recovery codes can only be viewed once."""
        # Setup and verify 2FA
        auth_client.get('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            import pyotp
            totp = pyotp.TOTP(user.totp_secret)
            valid_code = totp.now()

        auth_client.post('/settings/2fa/verify', data={'code': valid_code})

        # First visit shows codes
        response1 = auth_client.get('/settings/2fa/recovery-codes')
        assert response1.status_code == 200

        # Second visit redirects with message
        response2 = auth_client.get('/settings/2fa/recovery-codes', follow_redirects=True)
        assert b'already been shown' in response2.data.lower()

    def test_recovery_codes_redirect_without_session(self, auth_client):
        """Test recovery codes page redirects without session data."""
        response = auth_client.get('/settings/2fa/recovery-codes', follow_redirects=True)
        assert response.status_code == 200
        # Should redirect with message about already shown
        assert b'already been shown' in response.data.lower()


# ============================================================================
# H. 2FA Disable
# ============================================================================

class Test2FADisable:
    """Tests for 2FA disable functionality."""

    def _enable_2fa(self, auth_client, app, user_id):
        """Helper to enable 2FA for a user."""
        auth_client.get('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, user_id)
            import pyotp
            totp = pyotp.TOTP(user.totp_secret)
            valid_code = totp.now()

        auth_client.post('/settings/2fa/verify', data={'code': valid_code})
        auth_client.get('/settings/2fa/recovery-codes')  # Clear session

    def test_disable_2fa_success(self, auth_client, app, test_user):
        """Test disabling 2FA with correct password."""
        self._enable_2fa(auth_client, app, test_user['id'])

        response = auth_client.post('/settings/2fa/disable', data={
            'password': test_user['password']
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'disabled' in response.data.lower()

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.totp_enabled is False

    def test_disable_2fa_wrong_password(self, auth_client, app, test_user):
        """Test disabling 2FA with wrong password."""
        self._enable_2fa(auth_client, app, test_user['id'])

        response = auth_client.post('/settings/2fa/disable', data={
            'password': 'WrongPassword123!'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'incorrect' in response.data.lower()

        # 2FA should still be enabled
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.totp_enabled is True

    def test_disable_2fa_not_enabled(self, auth_client, test_user):
        """Test disabling 2FA when not enabled."""
        response = auth_client.post('/settings/2fa/disable', data={
            'password': test_user['password']
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'not enabled' in response.data.lower()


# ============================================================================
# I. Multi-User Isolation
# ============================================================================

class TestSettingsUserIsolation:
    """Tests for multi-user data isolation in settings."""

    def test_user_sees_own_email_on_settings(self, auth_client, test_user):
        """Test user sees their own email on settings page."""
        response = auth_client.get('/settings/')
        assert response.status_code == 200
        assert test_user['email'].encode() in response.data

    def test_admin_sees_own_email_on_settings(self, admin_client, admin_user):
        """Test admin sees their own email on settings page."""
        response = admin_client.get('/settings/')
        assert response.status_code == 200
        assert admin_user['email'].encode() in response.data

    def test_2fa_secret_generated_per_user(self, auth_client, app, test_user):
        """Test that 2FA secret is generated uniquely for each user."""
        auth_client.get('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            secret1 = user.totp_secret
            assert secret1 is not None, "User should have TOTP secret after setup"
            assert len(secret1) >= 16, "TOTP secret should be at least 16 characters"

        # POST to regenerate
        auth_client.post('/settings/2fa/setup')

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            secret2 = user.totp_secret
            assert secret2 is not None
            # After POST, secret should be regenerated
            assert secret2 != secret1, "Secret should change after POST regeneration"

    def test_user_cannot_change_other_users_password(self, app, test_user, admin_user):
        """Test user cannot change another user's password by manipulating forms."""
        # Login as test user
        client = app.test_client()
        client.post('/auth/login', data={
            'email': test_user['email'],
            'password': test_user['password']
        })

        # Try to change password with correct current password
        # This should only affect the logged-in user (test_user)
        new_password = 'NewSecureP@ss123!'
        client.post('/settings/password', data={
            'current_password': test_user['password'],
            'new_password': new_password,
            'confirm_password': new_password
        })

        # Admin user's password should be unchanged
        with app.app_context():
            admin = db.session.get(User, admin_user['id'])
            assert admin.check_password(admin_user['password'])
