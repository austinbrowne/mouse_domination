"""Tests for utility modules."""
import pytest
from flask import Flask
from utils.validation import (
    ValidationError, validate_required, validate_email, validate_url,
    validate_foreign_key, parse_date, parse_int, parse_float, or_none
)
from utils.routes import FormData, handle_form_errors, get_request_id
from models import Company
from extensions import db


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error_with_message(self):
        """Test ValidationError with message."""
        # ValidationError(field, message)
        error = ValidationError("name", "Invalid value")
        assert error.message == "Invalid value"
        assert error.field == "name"

    def test_validation_error_str(self):
        """Test ValidationError string representation."""
        error = ValidationError("name", "Invalid value")
        assert str(error) == "name: Invalid value"


class TestValidateRequired:
    """Tests for validate_required function."""

    def test_required_valid(self):
        """Test valid required value."""
        result = validate_required("test value", "name")
        assert result == "test value"

    def test_required_empty_string(self):
        """Test empty string raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            validate_required("", "name")
        assert exc.value.field == "name"

    def test_required_whitespace(self):
        """Test whitespace-only raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_required("   ", "name")

    def test_required_strips_whitespace(self):
        """Test whitespace is stripped from value."""
        result = validate_required("  test  ", "name")
        assert result == "test"

    def test_required_max_length(self):
        """Test max_length validation."""
        with pytest.raises(ValidationError) as exc:
            validate_required("long value", "name", max_length=5)
        assert "5 characters" in exc.value.message


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_email_valid(self):
        """Test valid email."""
        result = validate_email("test@example.com", "email")
        assert result == "test@example.com"

    def test_email_invalid_format(self):
        """Test invalid email format."""
        with pytest.raises(ValidationError) as exc:
            validate_email("not-an-email", "email")
        assert exc.value.field == "email"

    def test_email_empty_returns_none(self):
        """Test empty email returns None."""
        result = validate_email("", "email")
        assert result is None


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_url_valid_http(self):
        """Test valid HTTP URL."""
        result = validate_url("http://example.com", "url")
        assert result == "http://example.com"

    def test_url_valid_https(self):
        """Test valid HTTPS URL."""
        result = validate_url("https://example.com/path", "url")
        assert result == "https://example.com/path"

    def test_url_empty_returns_none(self):
        """Test empty URL returns None."""
        result = validate_url("", "url")
        assert result is None


class TestParseFunctions:
    """Tests for parse_date, parse_int, parse_float."""

    def test_parse_date_valid(self):
        """Test parsing valid date."""
        result = parse_date("2024-01-15", "date")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_empty(self):
        """Test empty date returns None."""
        result = parse_date("", "date")
        assert result is None

    def test_parse_int_valid(self):
        """Test parsing valid integer."""
        result = parse_int("42", "count")
        assert result == 42

    def test_parse_int_empty(self):
        """Test empty int returns None."""
        result = parse_int("", "count")
        assert result is None

    def test_parse_int_negative_blocked(self):
        """Test negative int blocked by default."""
        with pytest.raises(ValidationError):
            parse_int("-5", "count", allow_negative=False)

    def test_parse_int_negative_allowed(self):
        """Test negative int allowed when specified."""
        result = parse_int("-5", "count", allow_negative=True)
        assert result == -5

    def test_parse_float_valid(self):
        """Test parsing valid float."""
        result = parse_float("3.14", "price")
        assert result == pytest.approx(3.14)

    def test_parse_float_empty(self):
        """Test empty float returns None."""
        result = parse_float("", "price")
        assert result is None


class TestOrNone:
    """Tests for or_none helper."""

    def test_or_none_with_value(self):
        """Test or_none returns value when present."""
        assert or_none("test") == "test"

    def test_or_none_empty_string(self):
        """Test or_none returns None for empty string."""
        assert or_none("") is None

    def test_or_none_whitespace(self):
        """Test or_none returns None for whitespace."""
        assert or_none("   ") is None


class TestFormData:
    """Tests for FormData helper class."""

    def test_required_valid(self, app):
        """Test FormData.required with valid value."""
        with app.test_request_context():
            form = FormData({'name': 'Test'})
            result = form.required('name')
            assert result == 'Test'

    def test_required_empty(self, app):
        """Test FormData.required raises on empty."""
        with app.test_request_context():
            form = FormData({'name': ''})
            with pytest.raises(ValidationError):
                form.required('name')

    def test_optional_with_value(self, app):
        """Test FormData.optional with value."""
        with app.test_request_context():
            form = FormData({'notes': 'Some notes'})
            result = form.optional('notes')
            assert result == 'Some notes'

    def test_optional_empty(self, app):
        """Test FormData.optional returns None for empty."""
        with app.test_request_context():
            form = FormData({'notes': ''})
            result = form.optional('notes')
            assert result is None

    def test_choice_valid(self, app):
        """Test FormData.choice with valid choice."""
        with app.test_request_context():
            form = FormData({'status': 'active'})
            result = form.choice('status', ['active', 'inactive'])
            assert result == 'active'

    def test_choice_invalid(self, app):
        """Test FormData.choice returns default for invalid."""
        with app.test_request_context():
            form = FormData({'status': 'invalid'})
            result = form.choice('status', ['active', 'inactive'], default='active')
            assert result == 'active'

    def test_boolean_true_values(self, app):
        """Test FormData.boolean with true values."""
        with app.test_request_context():
            for val in ['yes', 'true', '1', 'on', 'YES', 'True']:
                form = FormData({'flag': val})
                assert form.boolean('flag') is True

    def test_boolean_false_values(self, app):
        """Test FormData.boolean with false values."""
        with app.test_request_context():
            for val in ['', 'no', 'false', '0', 'off']:
                form = FormData({'flag': val})
                assert form.boolean('flag') is False

    def test_integer_valid(self, app):
        """Test FormData.integer with valid value."""
        with app.test_request_context():
            form = FormData({'count': '42'})
            result = form.integer('count')
            assert result == 42

    def test_decimal_valid(self, app):
        """Test FormData.decimal with valid value."""
        with app.test_request_context():
            form = FormData({'price': '9.99'})
            result = form.decimal('price')
            assert result == pytest.approx(9.99)

    def test_date_valid(self, app):
        """Test FormData.date with valid value."""
        with app.test_request_context():
            form = FormData({'date': '2024-01-15'})
            result = form.date('date')
            assert result is not None
            assert result.year == 2024

    def test_foreign_key_valid(self, app, company):
        """Test FormData.foreign_key with valid ID."""
        with app.test_request_context():
            form = FormData({'company_id': str(company['id'])})
            result = form.foreign_key('company_id', Company)
            assert result == company['id']

    def test_foreign_key_invalid(self, app):
        """Test FormData.foreign_key with invalid ID."""
        with app.test_request_context():
            form = FormData({'company_id': '99999'})
            with pytest.raises(ValidationError):
                form.foreign_key('company_id', Company)

    def test_to_dict(self, app):
        """Test FormData.to_dict extracts multiple fields."""
        with app.test_request_context():
            form = FormData({'name': 'Test', 'notes': 'Some notes', 'extra': ''})
            result = form.to_dict('name', 'notes', 'extra')
            assert result == {'name': 'Test', 'notes': 'Some notes', 'extra': None}


class TestGetRequestId:
    """Tests for get_request_id helper."""

    def test_get_request_id_exists(self, app):
        """Test get_request_id when set."""
        with app.test_request_context():
            from flask import g
            g.request_id = 'test-123'
            result = get_request_id()
            assert result == 'test-123'

    def test_get_request_id_fallback(self, app):
        """Test get_request_id generates fallback."""
        with app.test_request_context():
            result = get_request_id()
            # Should return an 8-char string
            assert len(result) == 8
