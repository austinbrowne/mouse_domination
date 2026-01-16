import io
import base64
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from routes.auth import validate_password_strength

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/')
@login_required
def index():
    """User settings page."""
    # Get recent login history (last 10)
    login_history = current_user.login_history.limit(10).all()
    return render_template('settings/index.html', login_history=login_history)


@settings_bp.route('/profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile (name)."""
    name = request.form.get('name', '').strip()

    # Name can be empty (optional field)
    if name and len(name) > 100:
        flash('Name must be 100 characters or less.', 'error')
        return redirect(url_for('settings.index'))

    try:
        current_user.name = name if name else None
        db.session.commit()
        flash('Profile updated successfully.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('settings.index'))


@settings_bp.route('/password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validate current password
    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('settings.index'))

    # Validate new password matches confirmation
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings.index'))

    # Validate password strength
    password_errors = validate_password_strength(new_password)
    if password_errors:
        for error in password_errors:
            flash(error, 'error')
        return redirect(url_for('settings.index'))

    # Check new password is different from current
    if current_user.check_password(new_password):
        flash('New password must be different from current password.', 'error')
        return redirect(url_for('settings.index'))

    try:
        current_user.set_password(new_password)
        db.session.commit()
        flash('Password changed successfully.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('settings.index'))


@settings_bp.route('/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """Start 2FA setup - show QR code."""
    if current_user.totp_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('settings.index'))

    if request.method == 'POST':
        # Generate new secret
        current_user.generate_totp_secret()
        db.session.commit()

    if not current_user.totp_secret:
        # First visit - generate secret
        current_user.generate_totp_secret()
        db.session.commit()

    # Generate QR code
    import qrcode
    from flask import current_app

    app_name = current_app.config.get('APP_NAME', 'Creator Hub')
    uri = current_user.get_totp_uri(app_name)

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64 for embedding in HTML
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render_template('settings/setup_2fa.html',
                          qr_code=qr_code_base64,
                          secret=current_user.totp_secret)


@settings_bp.route('/2fa/verify', methods=['POST'])
@login_required
def verify_2fa():
    """Verify TOTP code and enable 2FA."""
    if current_user.totp_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('settings.index'))

    code = request.form.get('code', '').strip().replace(' ', '')

    if not code or len(code) != 6 or not code.isdigit():
        flash('Please enter a valid 6-digit code.', 'error')
        return redirect(url_for('settings.setup_2fa'))

    if not current_user.verify_totp(code):
        flash('Invalid code. Please try again.', 'error')
        return redirect(url_for('settings.setup_2fa'))

    # Enable 2FA and generate recovery codes
    current_user.enable_totp()
    recovery_codes = current_user.generate_recovery_codes()
    db.session.commit()

    # Store recovery codes in session for one-time display
    session['recovery_codes'] = recovery_codes

    return redirect(url_for('settings.show_recovery_codes'))


@settings_bp.route('/2fa/recovery-codes')
@login_required
def show_recovery_codes():
    """Show recovery codes (one-time only after setup)."""
    recovery_codes = session.pop('recovery_codes', None)
    if not recovery_codes:
        flash('Recovery codes have already been shown.', 'info')
        return redirect(url_for('settings.index'))

    return render_template('settings/recovery_codes.html', codes=recovery_codes)


@settings_bp.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    """Disable 2FA (requires password confirmation)."""
    if not current_user.totp_enabled:
        flash('Two-factor authentication is not enabled.', 'info')
        return redirect(url_for('settings.index'))

    password = request.form.get('password', '')
    if not current_user.check_password(password):
        flash('Incorrect password.', 'error')
        return redirect(url_for('settings.index'))

    current_user.disable_totp()
    db.session.commit()
    flash('Two-factor authentication has been disabled.', 'success')
    return redirect(url_for('settings.index'))
