"""Architecture tests for the Mouse Domination application."""
import pytest
from flask import g
from app import create_app, db
from config import TestConfig
from utils.routes import FormData, get_request_id
from utils.validation import ValidationError


class TestRequestID:
    """Test request ID generation and tracking."""

    def test_request_id_generated_per_request(self, app, client):
        """Test that each request gets a unique ID."""
        ids = []

        @app.route('/test-request-id')
        def test_endpoint():
            ids.append(g.request_id)
            return 'ok'

        # Make two requests
        client.get('/test-request-id')
        client.get('/test-request-id')

        # Should have two different IDs
        assert len(ids) == 2
        assert ids[0] != ids[1]
        assert len(ids[0]) == 8  # UUID prefix length

    def test_request_id_available_in_route(self, app, client):
        """Test that request ID is accessible in routes."""
        captured_id = []

        @app.route('/capture-id')
        def capture_id():
            captured_id.append(get_request_id())
            return 'ok'

        client.get('/capture-id')

        assert len(captured_id) == 1
        assert captured_id[0] is not None
        assert len(captured_id[0]) == 8


class TestFormData:
    """Test FormData helper class."""

    def test_required_field_present(self):
        """Test required field extraction when present."""
        form = FormData({'name': 'Test Name'})
        result = form.required('name')
        assert result == 'Test Name'

    def test_required_field_missing(self):
        """Test required field raises ValidationError when missing."""
        form = FormData({})
        with pytest.raises(ValidationError) as exc_info:
            form.required('name')
        assert exc_info.value.field == 'name'

    def test_required_field_empty(self):
        """Test required field raises ValidationError when empty."""
        form = FormData({'name': '   '})
        with pytest.raises(ValidationError):
            form.required('name')

    def test_required_field_max_length(self):
        """Test required field respects max_length."""
        form = FormData({'name': 'a' * 100})
        with pytest.raises(ValidationError) as exc_info:
            form.required('name', max_length=50)
        assert 'at most 50' in str(exc_info.value.message)

    def test_optional_field_present(self):
        """Test optional field extraction when present."""
        form = FormData({'notes': 'Some notes'})
        result = form.optional('notes')
        assert result == 'Some notes'

    def test_optional_field_missing(self):
        """Test optional field returns None when missing."""
        form = FormData({})
        result = form.optional('notes')
        assert result is None

    def test_optional_field_empty(self):
        """Test optional field returns None when empty."""
        form = FormData({'notes': '   '})
        result = form.optional('notes')
        assert result is None

    def test_email_valid(self):
        """Test email validation with valid email."""
        form = FormData({'email': 'test@example.com'})
        result = form.email('email')
        assert result == 'test@example.com'

    def test_email_invalid(self):
        """Test email validation with invalid email."""
        form = FormData({'email': 'not-an-email'})
        with pytest.raises(ValidationError):
            form.email('email')

    def test_email_empty(self):
        """Test email returns None when empty."""
        form = FormData({'email': ''})
        result = form.email('email')
        assert result is None

    def test_choice_valid(self):
        """Test choice validation with valid choice."""
        choices = ['active', 'inactive', 'pending']
        form = FormData({'status': 'active'})
        result = form.choice('status', choices, default='pending')
        assert result == 'active'

    def test_choice_invalid_uses_default(self):
        """Test choice validation returns default for invalid choice."""
        choices = ['active', 'inactive', 'pending']
        form = FormData({'status': 'invalid'})
        result = form.choice('status', choices, default='pending')
        assert result == 'pending'

    def test_choice_missing_uses_default(self):
        """Test choice returns default when field missing."""
        choices = ['active', 'inactive']
        form = FormData({})
        result = form.choice('status', choices, default='active')
        assert result == 'active'

    def test_integer_valid(self):
        """Test integer parsing with valid integer."""
        form = FormData({'count': '42'})
        result = form.integer('count')
        assert result == 42

    def test_integer_empty(self):
        """Test integer returns None when empty."""
        form = FormData({'count': ''})
        result = form.integer('count')
        assert result is None

    def test_integer_invalid(self):
        """Test integer raises ValidationError for invalid value."""
        form = FormData({'count': 'not-a-number'})
        with pytest.raises(ValidationError):
            form.integer('count')

    def test_decimal_valid(self):
        """Test decimal parsing with valid decimal."""
        form = FormData({'price': '19.99'})
        result = form.decimal('price')
        assert result == 19.99

    def test_boolean_true_values(self):
        """Test boolean parsing for true values."""
        for value in ['yes', 'true', '1', 'on', 'YES', 'True']:
            form = FormData({'active': value})
            assert form.boolean('active') is True

    def test_boolean_false_values(self):
        """Test boolean parsing for false values."""
        for value in ['no', 'false', '0', 'off', '', 'anything']:
            form = FormData({'active': value})
            assert form.boolean('active') is False

    def test_to_dict(self):
        """Test extracting multiple fields as dictionary."""
        form = FormData({
            'twitter': '@user',
            'discord': 'user#1234',
            'youtube': ''
        })
        result = form.to_dict('twitter', 'discord', 'youtube', 'missing')
        assert result == {
            'twitter': '@user',
            'discord': 'user#1234',
            'youtube': None,
            'missing': None
        }

    def test_date_valid(self):
        """Test date parsing with valid date."""
        form = FormData({'date': '2024-01-15'})
        result = form.date('date')
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_date_empty(self):
        """Test date returns None when empty."""
        form = FormData({'date': ''})
        result = form.date('date')
        assert result is None

    def test_url_valid(self):
        """Test URL validation with valid URL."""
        form = FormData({'website': 'https://example.com'})
        result = form.url('website')
        assert result == 'https://example.com'

    def test_url_invalid(self):
        """Test URL validation with invalid URL."""
        form = FormData({'website': 'not-a-url'})
        with pytest.raises(ValidationError):
            form.url('website')


class TestCodeOrganization:
    """Test code organization patterns."""

    def test_all_routes_have_blueprints(self, app):
        """Test that all routes are registered via blueprints."""
        # Get all registered endpoints
        rules = list(app.url_map.iter_rules())

        # Filter out static endpoint
        non_static_rules = [r for r in rules if r.endpoint != 'static']

        # All endpoints should be prefixed with blueprint name (contain .)
        for rule in non_static_rules:
            assert '.' in rule.endpoint, f"Endpoint {rule.endpoint} should be in a blueprint"

    def test_error_logging_utility_exists(self):
        """Test that error logging utility is available."""
        from utils.logging import log_exception
        assert callable(log_exception)

    def test_validation_utilities_exist(self):
        """Test that validation utilities are available."""
        from utils.validation import (
            validate_required, validate_email, validate_url,
            parse_date, parse_int, parse_float, or_none,
            ValidationError
        )
        # All should be callable
        assert callable(validate_required)
        assert callable(validate_email)
        assert callable(validate_url)

    def test_query_helpers_exist(self):
        """Test that query helper utilities are available."""
        from utils.queries import (
            get_companies_for_dropdown,
            get_contacts_for_dropdown
        )
        assert callable(get_companies_for_dropdown)
        assert callable(get_contacts_for_dropdown)
