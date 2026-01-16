import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from extensions import db, limiter
from models import User

auth_bp = Blueprint('auth', __name__)


def validate_password_strength(password: str) -> list[str]:
    """Validate password meets security requirements."""
    errors = []
    if len(password) < 12:
        errors.append('Password must be at least 12 characters')
    if not any(c.isupper() for c in password):
        errors.append('Password must contain at least one uppercase letter')
    if not any(c.islower() for c in password):
        errors.append('Password must contain at least one lowercase letter')
    if not any(c.isdigit() for c in password):
        errors.append('Password must contain at least one digit')
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        errors.append('Password must contain at least one special character')
    return errors


def is_safe_url(target):
    """Validate redirect URL to prevent open redirect attacks."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="Too many login attempts. Please wait a minute.")
def login():
    """Handle user login with brute force protection."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()

        # Timing-safe: always hash something to prevent user enumeration
        if user is None:
            User._ph.hash('dummy_password_for_timing')
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html')

        # Check if account is approved
        if not user.is_approved:
            flash('Your account is pending approval.', 'info')
            return redirect(url_for('auth.pending'))

        # Check account lockout
        if user.is_locked():
            # Handle both naive (from SQLite) and aware datetimes
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            remaining = (locked_until - datetime.now(timezone.utc)).total_seconds() // 60
            flash(f'Account locked. Try again in {int(remaining) + 1} minutes.', 'error')
            return render_template('auth/login.html')

        # Verify password
        if not user.check_password(password):
            user.record_failed_login()
            db.session.commit()

            remaining_attempts = max(0, 5 - user.failed_login_attempts)
            if remaining_attempts > 0:
                flash(f'Invalid email or password. {remaining_attempts} attempts remaining.', 'error')
            else:
                flash('Account locked due to too many failed attempts.', 'error')
            return render_template('auth/login.html')

        # Successful login
        user.record_successful_login()
        db.session.commit()

        login_user(user, remember=remember)

        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Handle user logout. POST-only to prevent CSRF via GET."""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour", error_message="Registration limit reached. Please try later.")
def register():
    """Handle new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        name = request.form.get('name', '').strip()

        # Validate email format
        if not email or not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/register.html')

        # Check existing user - don't reveal if email exists (prevents enumeration)
        if User.query.filter_by(email=email).first():
            # Log for admin awareness, but show same success message to user
            current_app.logger.info(f"Registration attempted for existing email: {email}")
            flash('Account created. Please wait for admin approval.', 'success')
            return redirect(url_for('auth.pending'))

        # Validate password match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        # Validate password strength
        password_errors = validate_password_strength(password)
        if password_errors:
            for error in password_errors:
                flash(error, 'error')
            return render_template('auth/register.html')

        # Create user (pending approval)
        try:
            user = User(email=email, name=name or None, is_approved=False)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash('Account created. Please wait for admin approval.', 'success')
            return redirect(url_for('auth.pending'))

        except SQLAlchemyError:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


@auth_bp.route('/pending')
def pending():
    """Show pending approval message."""
    return render_template('auth/pending.html')
