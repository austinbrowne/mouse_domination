from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import User

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


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
