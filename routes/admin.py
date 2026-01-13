from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from extensions import db
from models import User, CustomOption
from constants import BUILTIN_CHOICES, OPTION_TYPE_LABELS
from services.options import get_all_custom_options, get_option_types

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def index():
    """Admin dashboard landing page."""
    pending_count = User.query.filter_by(is_approved=False).count()
    custom_options_count = CustomOption.query.count()
    return render_template('admin/index.html',
                           pending_count=pending_count,
                           custom_options_count=custom_options_count)


@admin_bp.route('/users')
@login_required
@admin_required
def list_users():
    """List all users with pending/approved status."""
    pending = User.query.filter_by(is_approved=False).order_by(User.created_at.desc()).all()
    approved = User.query.filter_by(is_approved=True).order_by(User.email).all()
    return render_template('admin/users.html', pending=pending, approved=approved)


@admin_bp.route('/users/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_user(id):
    """Approve a pending user."""
    try:
        user = User.query.get_or_404(id)
        if user.is_approved:
            flash(f'{user.email} is already approved.', 'info')
        else:
            user.is_approved = True
            db.session.commit()
            flash(f'{user.email} has been approved.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('admin.list_users'))


@admin_bp.route('/users/<int:id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_user(id):
    """Reject and delete a pending user."""
    try:
        user = User.query.get_or_404(id)
        if user.id == current_user.id:
            flash('You cannot delete yourself.', 'error')
        elif user.is_admin:
            flash('Cannot delete admin users.', 'error')
        else:
            email = user.email
            db.session.delete(user)
            db.session.commit()
            flash(f'{email} has been rejected and removed.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('admin.list_users'))


@admin_bp.route('/users/<int:id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(id):
    """Toggle admin status for a user."""
    try:
        user = User.query.get_or_404(id)
        if user.id == current_user.id:
            flash('You cannot modify your own admin status.', 'error')
        else:
            user.is_admin = not user.is_admin
            db.session.commit()
            status = 'granted' if user.is_admin else 'revoked'
            flash(f'Admin privileges {status} for {user.email}.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('admin.list_users'))


# Custom Options Management
@admin_bp.route('/options')
@login_required
@admin_required
def list_options():
    """List all custom options grouped by type."""
    custom_options = get_all_custom_options()
    option_types = get_option_types()
    return render_template(
        'admin/options.html',
        custom_options=custom_options,
        option_types=option_types,
        option_type_labels=OPTION_TYPE_LABELS,
        builtin_choices=BUILTIN_CHOICES
    )


@admin_bp.route('/options/new', methods=['POST'])
@login_required
@admin_required
def create_option():
    """Create a new custom option."""
    option_type = request.form.get('option_type', '').strip()
    value = request.form.get('value', '').strip().lower().replace(' ', '_')
    label = request.form.get('label', '').strip()

    # Validation
    if not option_type or option_type not in OPTION_TYPE_LABELS:
        flash('Invalid option type.', 'error')
        return redirect(url_for('admin.list_options'))

    if not value or not label:
        flash('Value and label are required.', 'error')
        return redirect(url_for('admin.list_options'))

    if len(value) > 100 or len(label) > 100:
        flash('Value and label must be 100 characters or less.', 'error')
        return redirect(url_for('admin.list_options'))

    # Check if value conflicts with built-in
    for v, _ in BUILTIN_CHOICES.get(option_type, []):
        if v == value:
            flash(f'"{value}" is already a built-in option.', 'error')
            return redirect(url_for('admin.list_options'))

    try:
        option = CustomOption(
            option_type=option_type,
            value=value,
            label=label,
            created_by=current_user.id
        )
        db.session.add(option)
        db.session.commit()
        flash(f'Custom option "{label}" added successfully.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash(f'An option with value "{value}" already exists for this type.', 'error')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('admin.list_options'))


@admin_bp.route('/options/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_option(id):
    """Delete a custom option."""
    try:
        option = CustomOption.query.get_or_404(id)
        label = option.label
        db.session.delete(option)
        db.session.commit()
        flash(f'Custom option "{label}" deleted.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('admin.list_options'))
