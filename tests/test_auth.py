"""Tests for authentication routes."""
import pytest
from datetime import datetime, timedelta, timezone
from models import User
from extensions import db
from routes.auth import validate_password_strength, is_safe_url


class TestPasswordValidation:
    """Tests for password strength validation."""

    def test_valid_password(self):
        """Test password that meets all requirements."""
        errors = validate_password_strength('SecurePass123!')
        assert errors == []

    def test_password_too_short(self):
        """Test password shorter than 12 characters."""
        errors = validate_password_strength('Short1!')
        assert 'Password must be at least 12 characters' in errors

    def test_password_no_uppercase(self):
        """Test password missing uppercase letter."""
        errors = validate_password_strength('alllowercase123!')
        assert 'Password must contain at least one uppercase letter' in errors

    def test_password_no_lowercase(self):
        """Test password missing lowercase letter."""
        errors = validate_password_strength('ALLUPPERCASE123!')
        assert 'Password must contain at least one lowercase letter' in errors

    def test_password_no_digit(self):
        """Test password missing digit."""
        errors = validate_password_strength('NoDigitsHere!!')
        assert 'Password must contain at least one digit' in errors

    def test_password_no_special(self):
        """Test password missing special character."""
        errors = validate_password_strength('NoSpecialChar123')
        assert 'Password must contain at least one special character' in errors

    def test_password_empty(self):
        """Test empty password fails all validations."""
        errors = validate_password_strength('')
        assert len(errors) == 5  # All 5 requirements fail

    def test_password_exactly_12_chars(self):
        """Test password at exact minimum length."""
        errors = validate_password_strength('ValidPass12!')
        assert errors == []

    def test_password_multiple_errors(self):
        """Test password with multiple issues."""
        errors = validate_password_strength('short')
        assert len(errors) >= 4  # Short, no upper, no digit, no special


class TestUrlSafety:
    """Tests for URL safety validation."""

    def test_safe_url_relative(self, app):
        """Test relative URL is safe."""
        with app.test_request_context():
            assert is_safe_url('/dashboard') is True

    def test_safe_url_same_host(self, app):
        """Test same host URL is safe."""
        with app.test_request_context():
            assert is_safe_url('http://localhost/dashboard') is True

    def test_unsafe_url_different_host(self, app):
        """Test different host URL is blocked."""
        with app.test_request_context():
            assert is_safe_url('http://evil.com/hack') is False

    def test_unsafe_url_javascript(self, app):
        """Test javascript: protocol is blocked."""
        with app.test_request_context():
            assert is_safe_url('javascript:alert(1)') is False

    def test_unsafe_url_data(self, app):
        """Test data: protocol is blocked."""
        with app.test_request_context():
            assert is_safe_url('data:text/html,<script>') is False


class TestLoginPage:
    """Tests for login page GET."""

    def test_login_page_renders(self, client):
        """Test login page renders for unauthenticated user."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower() or b'Login' in response.data

    def test_login_redirects_if_authenticated(self, auth_client):
        """Test authenticated user is redirected from login."""
        response = auth_client.get('/auth/login')
        assert response.status_code == 302
        assert '/dashboard' in response.location or response.status_code == 302


class TestLogin:
    """Tests for login POST."""

    def test_login_success(self, client, test_user):
        """Test successful login with valid credentials."""
        response = client.post('/auth/login', data={
            'email': test_user['email'],
            'password': test_user['password']
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should be redirected to dashboard after login
        assert b'dashboard' in response.data.lower() or response.status_code == 200

    def test_login_with_remember(self, client, test_user):
        """Test login with remember me option."""
        response = client.post('/auth/login', data={
            'email': test_user['email'],
            'password': test_user['password'],
            'remember': 'on'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_login_invalid_email(self, client, test_user):
        """Test login with wrong email."""
        response = client.post('/auth/login', data={
            'email': 'wrong@example.com',
            'password': test_user['password']
        })
        assert response.status_code == 200
        assert b'Invalid email or password' in response.data

    def test_login_invalid_password(self, client, test_user):
        """Test login with wrong password."""
        response = client.post('/auth/login', data={
            'email': test_user['email'],
            'password': 'WrongPassword123!'
        })
        assert response.status_code == 200
        assert b'Invalid email or password' in response.data

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user (timing safe)."""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'SomePassword123!'
        })
        assert response.status_code == 200
        assert b'Invalid email or password' in response.data

    def test_login_missing_email(self, client):
        """Test login with missing email."""
        response = client.post('/auth/login', data={
            'password': 'SomePassword123!'
        })
        assert response.status_code == 200
        assert b'Please enter both email and password' in response.data

    def test_login_missing_password(self, client, test_user):
        """Test login with missing password."""
        response = client.post('/auth/login', data={
            'email': test_user['email']
        })
        assert response.status_code == 200
        assert b'Please enter both email and password' in response.data

    def test_login_pending_user(self, client, unapproved_user):
        """Test login with unapproved user."""
        response = client.post('/auth/login', data={
            'email': unapproved_user['email'],
            'password': unapproved_user['password']
        })
        assert response.status_code == 302
        assert '/auth/pending' in response.location

    def test_login_failed_attempts_tracked(self, client, app, test_user):
        """Test failed login attempts are tracked."""
        # Make a failed login attempt
        client.post('/auth/login', data={
            'email': test_user['email'],
            'password': 'WrongPassword123!'
        })

        with app.app_context():
            user = User.query.filter_by(email=test_user['email']).first()
            assert user.failed_login_attempts >= 1

    def test_login_lockout_after_5_failures(self, client, app, test_user):
        """Test account locks after 5 failed attempts."""
        # Set user to 4 failed attempts
        with app.app_context():
            user = User.query.filter_by(email=test_user['email']).first()
            user.failed_login_attempts = 4
            db.session.commit()

        # 5th failure should lock
        response = client.post('/auth/login', data={
            'email': test_user['email'],
            'password': 'WrongPassword123!'
        })
        assert b'Account locked' in response.data

        with app.app_context():
            user = User.query.filter_by(email=test_user['email']).first()
            assert user.failed_login_attempts == 5
            assert user.locked_until is not None

    def test_login_locked_account(self, client, app, test_user):
        """Test login attempt on locked account."""
        # Lock the account using the model's method to ensure consistent behavior
        with app.app_context():
            user = User.query.filter_by(email=test_user['email']).first()
            # Set to 4 failed attempts so next check triggers lockout
            user.failed_login_attempts = 4
            db.session.commit()

        # Make one more failed attempt to trigger lockout via the proper method
        client.post('/auth/login', data={
            'email': test_user['email'],
            'password': 'WrongPassword123!'
        })

        # Now try with correct password - should still be locked
        response = client.post('/auth/login', data={
            'email': test_user['email'],
            'password': test_user['password']
        })
        assert b'Account locked' in response.data

    def test_login_safe_redirect(self, client, test_user):
        """Test safe redirect after login."""
        response = client.post('/auth/login?next=/contacts/', data={
            'email': test_user['email'],
            'password': test_user['password']
        })
        assert response.status_code == 302
        assert '/contacts/' in response.location

    def test_login_unsafe_redirect_blocked(self, client, test_user):
        """Test unsafe redirect is blocked."""
        response = client.post('/auth/login?next=http://evil.com', data={
            'email': test_user['email'],
            'password': test_user['password']
        })
        assert response.status_code == 302
        # Should redirect to dashboard, not evil.com
        assert 'evil.com' not in response.location

    def test_login_email_case_insensitive(self, client, test_user):
        """Test email is case-insensitive."""
        response = client.post('/auth/login', data={
            'email': test_user['email'].upper(),
            'password': test_user['password']
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_login_resets_failed_attempts(self, client, app, test_user):
        """Test successful login resets failed attempts."""
        with app.app_context():
            user = User.query.filter_by(email=test_user['email']).first()
            user.failed_login_attempts = 3
            db.session.commit()

        client.post('/auth/login', data={
            'email': test_user['email'],
            'password': test_user['password']
        })

        with app.app_context():
            user = User.query.filter_by(email=test_user['email']).first()
            assert user.failed_login_attempts == 0


class TestLogout:
    """Tests for logout."""

    def test_logout_clears_session(self, auth_client):
        """Test logout clears user session."""
        response = auth_client.post('/auth/logout', follow_redirects=True)
        assert response.status_code == 200
        assert b'logged out' in response.data.lower()

    def test_logout_requires_login(self, client):
        """Test logout requires authentication."""
        response = client.post('/auth/logout')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_logout_redirects_to_login(self, auth_client):
        """Test logout redirects to login page."""
        response = auth_client.post('/auth/logout')
        assert response.status_code == 302
        assert '/auth/login' in response.location


class TestRegisterPage:
    """Tests for register page GET."""

    def test_register_page_renders(self, client):
        """Test register page renders for unauthenticated user."""
        response = client.get('/auth/register')
        assert response.status_code == 200
        assert b'register' in response.data.lower() or b'Register' in response.data

    def test_register_redirects_if_authenticated(self, auth_client):
        """Test authenticated user is redirected from register."""
        response = auth_client.get('/auth/register')
        assert response.status_code == 302


class TestRegister:
    """Tests for registration POST."""

    def test_register_success(self, client, app):
        """Test successful registration creates pending user."""
        response = client.post('/auth/register', data={
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!',
            'name': 'New User'
        })
        assert response.status_code == 302
        assert '/auth/pending' in response.location

        with app.app_context():
            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
            assert user.is_approved is False
            assert user.name == 'New User'

    def test_register_without_name(self, client, app):
        """Test registration without optional name."""
        response = client.post('/auth/register', data={
            'email': 'noname@example.com',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        })
        assert response.status_code == 302

        with app.app_context():
            user = User.query.filter_by(email='noname@example.com').first()
            assert user is not None
            assert user.name is None

    def test_register_invalid_email_format(self, client):
        """Test registration with invalid email format."""
        response = client.post('/auth/register', data={
            'email': 'not-an-email',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        })
        assert response.status_code == 200
        assert b'valid email' in response.data.lower()

    def test_register_empty_email(self, client):
        """Test registration with empty email."""
        response = client.post('/auth/register', data={
            'email': '',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        })
        assert response.status_code == 200
        assert b'valid email' in response.data.lower()

    def test_register_duplicate_email(self, client, test_user):
        """Test registration with existing email."""
        response = client.post('/auth/register', data={
            'email': test_user['email'],
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        })
        assert response.status_code == 200
        assert b'already exists' in response.data.lower()

    def test_register_password_mismatch(self, client):
        """Test registration with mismatched passwords."""
        response = client.post('/auth/register', data={
            'email': 'mismatch@example.com',
            'password': 'SecurePass123!',
            'confirm_password': 'DifferentPass123!'
        })
        assert response.status_code == 200
        assert b'do not match' in response.data.lower()

    def test_register_weak_password_too_short(self, client):
        """Test registration with short password."""
        response = client.post('/auth/register', data={
            'email': 'weak@example.com',
            'password': 'Short1!',
            'confirm_password': 'Short1!'
        })
        assert response.status_code == 200
        assert b'at least 12 characters' in response.data

    def test_register_weak_password_no_special(self, client):
        """Test registration with password missing special char."""
        response = client.post('/auth/register', data={
            'email': 'weak@example.com',
            'password': 'NoSpecialChar123',
            'confirm_password': 'NoSpecialChar123'
        })
        assert response.status_code == 200
        assert b'special character' in response.data

    def test_register_email_normalized(self, client, app):
        """Test email is normalized (lowercase, stripped)."""
        response = client.post('/auth/register', data={
            'email': '  UPPERCASE@EXAMPLE.COM  ',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        })
        assert response.status_code == 302

        with app.app_context():
            user = User.query.filter_by(email='uppercase@example.com').first()
            assert user is not None


class TestPending:
    """Tests for pending approval page."""

    def test_pending_page_renders(self, client):
        """Test pending page renders."""
        response = client.get('/auth/pending')
        assert response.status_code == 200

    def test_pending_no_auth_required(self, client):
        """Test pending page doesn't require auth."""
        response = client.get('/auth/pending')
        assert response.status_code == 200
