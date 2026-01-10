"""Route utilities for reducing code duplication in Flask routes."""
import uuid
from functools import wraps
from flask import request, flash, redirect, url_for, current_app, g
from sqlalchemy.exc import SQLAlchemyError
from app import db
from utils.logging import log_exception
from utils.validation import ValidationError


def get_request_id():
    """Get the request ID from Flask's g object.

    The request ID is set by app.before_request and persists
    for the duration of the request. Falls back to generating
    one if not set (e.g., in tests).
    """
    return getattr(g, 'request_id', str(uuid.uuid4())[:8])


def handle_form_errors(redirect_endpoint, **redirect_kwargs):
    """Decorator to handle ValidationError and SQLAlchemyError in form routes.

    Args:
        redirect_endpoint: The endpoint to redirect to on error (e.g., 'contacts.list_contacts')
        **redirect_kwargs: Additional kwargs to pass to url_for

    Usage:
        @handle_form_errors('contacts.list_contacts')
        def create_contact():
            # validation code that may raise ValidationError or SQLAlchemyError
            pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except ValidationError as e:
                flash(f'{e.field}: {e.message}', 'error')
                return redirect(url_for(redirect_endpoint, **redirect_kwargs))
            except SQLAlchemyError as e:
                db.session.rollback()
                request_id = get_request_id()
                log_exception(
                    current_app.logger,
                    f'{f.__name__} [req:{request_id}]',
                    e,
                    endpoint=request.endpoint
                )
                flash('Database error occurred. Please try again.', 'error')
                return redirect(url_for(redirect_endpoint, **redirect_kwargs))
        return wrapper
    return decorator


def db_operation(operation_name):
    """Decorator for database operations with automatic error handling and logging.

    Args:
        operation_name: Human-readable name for the operation (e.g., 'Create contact')

    Usage:
        @db_operation('Create contact')
        def save_contact(contact):
            db.session.add(contact)
            db.session.commit()
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except SQLAlchemyError as e:
                db.session.rollback()
                request_id = get_request_id()
                log_exception(
                    current_app.logger,
                    f'{operation_name} [req:{request_id}]',
                    e
                )
                raise
        return wrapper
    return decorator


class FormData:
    """Helper class for extracting and validating form data.

    Usage:
        form = FormData(request.form)
        name = form.required('name', max_length=100)
        email = form.optional('email')
        company_id = form.foreign_key('company_id', Company)
        status = form.choice('status', CHOICES, default='pending')
    """

    def __init__(self, form_data):
        """Initialize with form data (typically request.form)."""
        self.form = form_data
        self.errors = []

    def get(self, field, default=''):
        """Get raw form value."""
        return self.form.get(field, default)

    def required(self, field, max_length=None):
        """Get required field value, raising ValidationError if empty."""
        from utils.validation import validate_required
        value = self.form.get(field, '')
        return validate_required(value, field, max_length)

    def optional(self, field, strip=True):
        """Get optional field value, returning None if empty."""
        from utils.validation import or_none
        value = self.form.get(field, '')
        return or_none(value) if strip else value

    def email(self, field='email'):
        """Get and validate email field."""
        from utils.validation import validate_email
        return validate_email(self.form.get(field, ''), field)

    def url(self, field='url', max_length=2048):
        """Get and validate URL field."""
        from utils.validation import validate_url
        return validate_url(self.form.get(field, ''), field, max_length)

    def date(self, field):
        """Get and parse date field."""
        from utils.validation import parse_date
        return parse_date(self.form.get(field, ''), field)

    def integer(self, field, allow_negative=False):
        """Get and parse integer field."""
        from utils.validation import parse_int
        return parse_int(self.form.get(field, ''), field, allow_negative)

    def decimal(self, field, allow_negative=True):
        """Get and parse decimal/float field."""
        from utils.validation import parse_float
        return parse_float(self.form.get(field, ''), field, allow_negative)

    def choice(self, field, choices, default=None):
        """Get field value, ensuring it's one of the allowed choices."""
        value = self.form.get(field, default)
        if value and value not in choices:
            value = default
        return value

    def foreign_key(self, field, model_class):
        """Get and validate foreign key field."""
        from utils.validation import validate_foreign_key
        return validate_foreign_key(model_class, self.form.get(field, ''), field)

    def boolean(self, field):
        """Get boolean field (checkbox)."""
        value = self.form.get(field, '')
        return value.lower() in ('yes', 'true', '1', 'on')

    def to_dict(self, *fields):
        """Extract multiple optional fields as a dictionary."""
        return {field: self.optional(field) for field in fields}
