import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from extensions import db, limiter
from models import User, LoginHistory

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
            LoginHistory.record(
                user=user,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                success=False
            )
            db.session.commit()

            remaining_attempts = max(0, 5 - user.failed_login_attempts)
            if remaining_attempts > 0:
                flash(f'Invalid email or password. {remaining_attempts} attempts remaining.', 'error')
            else:
                flash('Account locked due to too many failed attempts.', 'error')
            return render_template('auth/login.html')

        # Check if 2FA is enabled
        if user.totp_enabled:
            # Store user info in session for 2FA verification
            session['2fa_user_id'] = user.id
            session['2fa_remember'] = remember
            session['2fa_next'] = request.args.get('next')
            return redirect(url_for('auth.verify_2fa_login'))

        # Successful login (no 2FA)
        user.record_successful_login()
        LoginHistory.record(
            user=user,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            success=True
        )
        db.session.commit()

        login_user(user, remember=remember)
        session.permanent = True  # Enable session timeout from PERMANENT_SESSION_LIFETIME

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


@auth_bp.route('/2fa-verify', methods=['GET', 'POST'])
@limiter.limit("10 per minute", error_message="Too many attempts. Please wait.")
def verify_2fa_login():
    """Verify 2FA code during login."""
    user_id = session.get('2fa_user_id')
    if not user_id:
        flash('Session expired. Please log in again.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user:
        session.pop('2fa_user_id', None)
        flash('Invalid session. Please log in again.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip().replace(' ', '').replace('-', '')
        use_recovery = request.form.get('use_recovery') == '1'

        if use_recovery:
            # Try recovery code
            if user.verify_recovery_code(code):
                # Success with recovery code
                remember = session.pop('2fa_remember', False)
                next_page = session.pop('2fa_next', None)
                session.pop('2fa_user_id', None)

                user.record_successful_login()
                LoginHistory.record(
                    user=user,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    success=True
                )
                db.session.commit()

                login_user(user, remember=remember)
                session.permanent = True  # Enable session timeout
                flash('Logged in with recovery code. Consider generating new recovery codes.', 'info')

                if next_page and is_safe_url(next_page):
                    return redirect(next_page)
                return redirect(url_for('main.dashboard'))
            else:
                flash('Invalid recovery code.', 'error')
                return render_template('auth/verify_2fa.html', use_recovery=True)
        else:
            # Try TOTP code
            if len(code) == 6 and code.isdigit() and user.verify_totp(code):
                # Success with TOTP
                remember = session.pop('2fa_remember', False)
                next_page = session.pop('2fa_next', None)
                session.pop('2fa_user_id', None)

                user.record_successful_login()
                LoginHistory.record(
                    user=user,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    success=True
                )
                db.session.commit()

                login_user(user, remember=remember)
                session.permanent = True  # Enable session timeout

                if next_page and is_safe_url(next_page):
                    return redirect(next_page)
                return redirect(url_for('main.dashboard'))
            else:
                flash('Invalid code. Please try again.', 'error')
                return render_template('auth/verify_2fa.html', use_recovery=False)

    return render_template('auth/verify_2fa.html', use_recovery=False)


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
            user = User(email=email, name=name or None, is_approved=False, email_verified=False)
            user.set_password(password)
            db.session.add(user)

            # Generate email verification token and send
            token = user.generate_email_verification_token()
            db.session.commit()

            from utils.email import send_email_verification
            send_email_verification(user, token)

            flash('Account created. Please check your email to verify your address, then wait for admin approval.', 'success')
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


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per hour", error_message="Too many reset requests. Please try later.")
def forgot_password():
    """Handle forgot password requests."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('auth/forgot_password.html')

        user = User.query.filter_by(email=email).first()

        # Always show success to prevent email enumeration
        # But only send email if user exists
        if user and user.is_approved:
            token = user.generate_password_reset_token()
            db.session.commit()

            from utils.email import send_password_reset_email
            send_password_reset_email(user, token)

        flash('If an account exists with that email, you will receive a password reset link.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="Too many reset attempts. Please wait.")
def reset_password(token):
    """Handle password reset with token."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Find user by token
    user = User.query.filter_by(password_reset_token=token).first()

    if not user or not user.verify_password_reset_token(token):
        flash('Invalid or expired password reset link.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)

        password_errors = validate_password_strength(password)
        if password_errors:
            for error in password_errors:
                flash(error, 'error')
            return render_template('auth/reset_password.html', token=token)

        try:
            user.set_password(password)
            user.clear_password_reset_token()
            # Also unlock account if it was locked
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()

            flash('Your password has been reset. You can now log in.', 'success')
            return redirect(url_for('auth.login'))

        except SQLAlchemyError:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
            return render_template('auth/reset_password.html', token=token)

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/verify-email/<token>')
@limiter.limit("10 per minute", error_message="Too many verification attempts. Please wait.")
def verify_email(token):
    """Verify user's email address."""
    user = User.query.filter_by(email_verification_token=token).first()

    if not user:
        flash('Invalid verification link.', 'error')
        return redirect(url_for('auth.login'))

    if not user.verify_email_verification_token(token):
        flash('Verification link has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.resend_verification'))

    try:
        user.mark_email_verified()
        db.session.commit()
        flash('Email verified successfully! Your account is pending admin approval.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
@limiter.limit("3 per hour", error_message="Too many verification requests. Please try later.")
def resend_verification():
    """Resend email verification link."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('auth/resend_verification.html')

        user = User.query.filter_by(email=email).first()

        # Always show success to prevent email enumeration
        if user and not user.email_verified:
            token = user.generate_email_verification_token()
            db.session.commit()

            from utils.email import send_email_verification
            send_email_verification(user, token)

        flash('If an account exists with that email and is not yet verified, you will receive a verification link.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/resend_verification.html')
