"""Security tests for the Mouse Domination application."""
import pytest
from app import create_app, db
from config import TestConfig, DevelopmentConfig, ProductionConfig
from models import Contact, Company, OutreachTemplate
from utils.validation import (
    validate_url, validate_required, validate_length,
    validate_email, ValidationError
)


class TestSecurityHeaders:
    """Test security headers are properly set."""

    def test_x_frame_options_header(self, client):
        """Test X-Frame-Options header is set."""
        response = client.get('/')
        assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'

    def test_x_content_type_options_header(self, client):
        """Test X-Content-Type-Options header is set."""
        response = client.get('/')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_xss_protection_header(self, client):
        """Test X-XSS-Protection header is set."""
        response = client.get('/')
        assert response.headers.get('X-XSS-Protection') == '1; mode=block'

    def test_referrer_policy_header(self, client):
        """Test Referrer-Policy header is set."""
        response = client.get('/')
        assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


class TestCSRFProtection:
    """Test CSRF protection."""

    def test_post_without_csrf_fails(self, csrf_client):
        """Test that POST requests without CSRF token fail when CSRF is enabled."""
        response = csrf_client.post('/contacts/new', data={
            'name': 'Test Contact',
            'email': 'test@example.com'
        })
        # Should get a 400 Bad Request due to missing CSRF
        assert response.status_code == 400

    def test_post_with_csrf_succeeds(self, csrf_client):
        """Test that POST requests with valid CSRF token succeed."""
        from tests.conftest import get_csrf_token

        # Get a CSRF token from the form page
        token = get_csrf_token(csrf_client, '/contacts/new')
        assert token is not None, "Failed to get CSRF token"

        response = csrf_client.post('/contacts/new', data={
            'csrf_token': token,
            'name': 'Test Contact',
            'email': 'test@example.com',
            'role': 'other',
            'relationship_status': 'cold'
        })
        # Should redirect on success (302) or show form with success message
        assert response.status_code in [200, 302]

    def test_delete_without_csrf_fails(self, csrf_app, csrf_client):
        """Test that DELETE (POST) requests without CSRF fail."""
        with csrf_app.app_context():
            # Create a contact first
            contact = Contact(name='Test', email='test@test.com')
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id

            # Try to delete without CSRF
            response = csrf_client.post(f'/contacts/{contact_id}/delete')
            assert response.status_code == 400


class TestURLValidation:
    """Test URL validation security."""

    def test_valid_https_url(self):
        """Test valid HTTPS URL passes."""
        result = validate_url('https://example.com/path', 'url')
        assert result == 'https://example.com/path'

    def test_valid_http_url(self):
        """Test valid HTTP URL passes."""
        result = validate_url('http://example.com', 'url')
        assert result == 'http://example.com'

    def test_url_with_query_params(self):
        """Test URL with query parameters passes."""
        result = validate_url('https://example.com/path?q=test&page=1', 'url')
        assert result == 'https://example.com/path?q=test&page=1'

    def test_empty_url_returns_none(self):
        """Test empty URL returns None."""
        assert validate_url('', 'url') is None
        assert validate_url('   ', 'url') is None

    def test_javascript_url_blocked(self):
        """Test javascript: URLs are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            validate_url('javascript:alert(1)', 'url')
        assert 'Invalid URL' in str(exc_info.value)

    def test_data_url_blocked(self):
        """Test data: URLs are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            validate_url('data:text/html,<script>alert(1)</script>', 'url')
        assert 'Invalid URL' in str(exc_info.value)

    def test_url_without_protocol_fails(self):
        """Test URL without protocol fails."""
        with pytest.raises(ValidationError):
            validate_url('www.example.com', 'url')

    def test_url_max_length(self):
        """Test URL max length validation."""
        long_url = 'https://example.com/' + 'a' * 3000
        with pytest.raises(ValidationError) as exc_info:
            validate_url(long_url, 'url')
        assert 'at most' in str(exc_info.value)

    def test_invalid_url_format(self):
        """Test invalid URL format fails."""
        with pytest.raises(ValidationError):
            validate_url('not-a-url', 'url')


class TestInputLengthValidation:
    """Test input length validation."""

    def test_validate_required_with_max_length(self):
        """Test validate_required respects max_length."""
        result = validate_required('test', 'field', max_length=10)
        assert result == 'test'

        with pytest.raises(ValidationError) as exc_info:
            validate_required('a' * 100, 'field', max_length=50)
        assert 'at most 50' in str(exc_info.value)

    def test_validate_length(self):
        """Test validate_length function."""
        result = validate_length('test', 'field', min_length=2, max_length=10)
        assert result == 'test'

        with pytest.raises(ValidationError) as exc_info:
            validate_length('a', 'field', min_length=5)
        assert 'at least 5' in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            validate_length('a' * 20, 'field', max_length=10)
        assert 'at most 10' in str(exc_info.value)

    def test_validate_length_empty_returns_none(self):
        """Test validate_length returns None for empty values."""
        assert validate_length('', 'field', max_length=10) is None
        assert validate_length('   ', 'field', max_length=10) is None


class TestEmailValidation:
    """Test email validation security."""

    def test_valid_email(self):
        """Test valid email passes."""
        assert validate_email('test@example.com') == 'test@example.com'
        assert validate_email('user.name+tag@domain.co.uk') == 'user.name+tag@domain.co.uk'

    def test_invalid_email(self):
        """Test invalid email fails."""
        with pytest.raises(ValidationError):
            validate_email('not-an-email')

        with pytest.raises(ValidationError):
            validate_email('missing@domain')

    def test_empty_email_returns_none(self):
        """Test empty email returns None."""
        assert validate_email('') is None


class TestXSSPrevention:
    """Test XSS prevention in template preview."""

    def test_template_preview_escapes_contact_name(self, app, client):
        """Test that contact names are escaped in template preview."""
        with app.app_context():
            # Create a contact with XSS payload in name
            contact = Contact(
                name='<script>alert("xss")</script>',
                email='test@example.com'
            )
            db.session.add(contact)
            db.session.commit()

            # Create a template with placeholder
            template = OutreachTemplate(
                name='Test Template',
                category='other',
                body='Hello {{contact_name}}, welcome!'
            )
            db.session.add(template)
            db.session.commit()

            # Preview the template with the contact
            response = client.get(f'/templates/{template.id}/preview?contact_id={contact.id}')
            assert response.status_code == 200

            # The script tag should be escaped in the response
            response_text = response.data.decode('utf-8')
            assert '<script>alert' not in response_text
            assert '&lt;script&gt;' in response_text or 'alert' not in response_text

    def test_template_preview_escapes_company_name(self, app, client):
        """Test that company names are escaped in template preview."""
        with app.app_context():
            # Create a company with XSS payload in name
            company = Company(
                name='<img src=x onerror=alert(1)>',
                category='other'
            )
            db.session.add(company)
            db.session.commit()

            # Create a template with placeholder
            template = OutreachTemplate(
                name='Test Template',
                category='other',
                body='Working with {{company_name}}'
            )
            db.session.add(template)
            db.session.commit()

            # Preview the template with the company
            response = client.get(f'/templates/{template.id}/preview?company_id={company.id}')
            assert response.status_code == 200

            # The XSS payload should be escaped - angle brackets become entities
            response_text = response.data.decode('utf-8')
            # The raw <img should be escaped to &lt;img (or double-escaped)
            # Either escaped form is acceptable
            assert '<img src=x onerror' not in response_text, "Unescaped XSS vector found"
            assert '&lt;img' in response_text or '&amp;lt;img' in response_text, "Escaped company name not found"


class TestConfigurationSecurity:
    """Test configuration security settings."""

    def test_debug_disabled_by_default(self):
        """Test debug mode is disabled in base config."""
        from config import Config
        assert Config.DEBUG is False

    def test_development_config_debug_enabled(self):
        """Test debug mode is enabled in development."""
        assert DevelopmentConfig.DEBUG is True

    def test_production_config_debug_disabled(self):
        """Test debug mode is disabled in production."""
        assert ProductionConfig.DEBUG is False

    def test_session_cookie_httponly(self):
        """Test session cookie is httponly."""
        from config import Config
        assert Config.SESSION_COOKIE_HTTPONLY is True

    def test_session_cookie_samesite(self):
        """Test session cookie samesite policy."""
        from config import Config
        assert Config.SESSION_COOKIE_SAMESITE == 'Lax'

    def test_max_content_length_set(self):
        """Test max content length is set."""
        from config import Config
        assert Config.MAX_CONTENT_LENGTH is not None
        assert Config.MAX_CONTENT_LENGTH > 0
        # Should be reasonable (16MB or less)
        assert Config.MAX_CONTENT_LENGTH <= 16 * 1024 * 1024

    def test_test_config_csrf_disabled(self):
        """Test CSRF is disabled in test config for easier testing."""
        assert TestConfig.WTF_CSRF_ENABLED is False


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""

    def test_search_parameter_safe(self, app, client):
        """Test search parameters are safely handled."""
        with app.app_context():
            # Try SQL injection in search parameter
            response = client.get("/contacts/?search=' OR '1'='1")
            assert response.status_code == 200

            # Try another SQL injection attempt
            response = client.get("/contacts/?search='; DROP TABLE contacts; --")
            assert response.status_code == 200

    def test_id_parameter_validated(self, client):
        """Test ID parameters reject non-numeric values."""
        # Non-numeric ID should return 404
        response = client.get('/contacts/abc/edit')
        assert response.status_code == 404

        # SQL injection in ID should return 404
        response = client.get("/contacts/1; DROP TABLE contacts/edit")
        assert response.status_code == 404


class TestRequestSizeLimits:
    """Test request size limits."""

    def test_max_content_length_configured(self, app):
        """Test max content length is configured."""
        assert app.config['MAX_CONTENT_LENGTH'] is not None
        assert app.config['MAX_CONTENT_LENGTH'] == 16 * 1024 * 1024
