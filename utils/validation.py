"""Input validation utilities for form processing."""
import re
from datetime import datetime, date
from functools import wraps
from flask import flash, redirect, request


class ValidationError(Exception):
    """Raised when validation fails."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def parse_date(value: str, field_name: str = 'date') -> date | None:
    """Safely parse a date string, returning None if empty or invalid."""
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError(field_name, f"Invalid date format. Use YYYY-MM-DD.")


def parse_float(value: str, field_name: str = 'value', allow_negative: bool = True) -> float | None:
    """Safely parse a float, returning None if empty."""
    if not value or not value.strip():
        return None
    try:
        result = float(value.strip())
        if not allow_negative and result < 0:
            raise ValidationError(field_name, "Value cannot be negative.")
        return result
    except ValueError:
        raise ValidationError(field_name, "Invalid number format.")


def parse_int(value: str, field_name: str = 'value', allow_negative: bool = False) -> int | None:
    """Safely parse an integer, returning None if empty."""
    if not value or not value.strip():
        return None
    try:
        result = int(value.strip())
        if not allow_negative and result < 0:
            raise ValidationError(field_name, "Value cannot be negative.")
        return result
    except ValueError:
        raise ValidationError(field_name, "Invalid integer format.")


def validate_required(value: str, field_name: str) -> str:
    """Validate that a required field is not empty."""
    if not value or not value.strip():
        raise ValidationError(field_name, "This field is required.")
    return value.strip()


def validate_email(value: str, field_name: str = 'email') -> str | None:
    """Validate email format, returning None if empty."""
    if not value or not value.strip():
        return None
    value = value.strip()
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, value):
        raise ValidationError(field_name, "Invalid email format.")
    return value


def validate_url(value: str, field_name: str = 'url') -> str | None:
    """Validate URL format, returning None if empty."""
    if not value or not value.strip():
        return None
    value = value.strip()
    # Basic URL pattern - allows http, https, or just starting with www
    pattern = r'^(https?://|www\.)[^\s]+$'
    if not re.match(pattern, value, re.IGNORECASE):
        raise ValidationError(field_name, "Invalid URL format. Must start with http://, https://, or www.")
    return value


def validate_range(value: float | int, min_val: float = None, max_val: float = None, field_name: str = 'value') -> float | int:
    """Validate that a numeric value is within range."""
    if min_val is not None and value < min_val:
        raise ValidationError(field_name, f"Value must be at least {min_val}.")
    if max_val is not None and value > max_val:
        raise ValidationError(field_name, f"Value must be at most {max_val}.")
    return value


def validate_choice(value: str, choices: list, field_name: str = 'value') -> str:
    """Validate that a value is one of the allowed choices."""
    if value not in choices:
        raise ValidationError(field_name, f"Invalid choice. Must be one of: {', '.join(choices)}")
    return value


def validate_foreign_key(model_class, value: str | int, field_name: str = 'id') -> int | None:
    """Validate that a foreign key references an existing record."""
    if not value:
        return None
    try:
        id_val = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field_name, "Invalid ID format.")

    record = model_class.query.get(id_val)
    if not record:
        raise ValidationError(field_name, f"Referenced {model_class.__name__} does not exist.")
    return id_val


def or_none(value: str) -> str | None:
    """Return None if value is empty, otherwise stripped value."""
    if not value or not value.strip():
        return None
    return value.strip()


def handle_validation_errors(redirect_url_func):
    """Decorator to handle validation errors in routes."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except ValidationError as e:
                flash(f'{e.field}: {e.message}', 'error')
                return redirect(redirect_url_func(*args, **kwargs))
        return wrapper
    return decorator
