"""Podcast access control utilities.

This module provides helpers and decorators for managing podcast access control.
Users can have two roles on a podcast:
- 'admin': Can edit podcast settings, add/remove members, full episode/template access
- 'contributor': Can create/edit episodes and templates, but not manage podcast settings
"""
from functools import wraps
from flask import abort, flash, redirect, url_for, g
from flask_login import current_user


def get_user_podcasts(user_id=None):
    """Get all podcasts the user has access to (any role).

    Args:
        user_id: User ID to check. Defaults to current_user.id.

    Returns:
        List of Podcast objects the user has access to.
    """
    from models import Podcast, PodcastMember

    if user_id is None:
        if not current_user.is_authenticated:
            return []
        user_id = current_user.id

    # Get all podcast IDs user is a member of
    member_podcast_ids = PodcastMember.query.filter_by(
        user_id=user_id
    ).with_entities(PodcastMember.podcast_id).all()

    podcast_ids = [m.podcast_id for m in member_podcast_ids]

    if not podcast_ids:
        return []

    return Podcast.query.filter(
        Podcast.id.in_(podcast_ids),
        Podcast.is_active == True
    ).order_by(Podcast.name).all()


def get_user_role(podcast_id, user_id=None):
    """Get user's role on a podcast.

    Args:
        podcast_id: ID of the podcast to check.
        user_id: User ID to check. Defaults to current_user.id.

    Returns:
        'admin', 'contributor', or None if no access.
    """
    from models import PodcastMember

    if user_id is None:
        if not current_user.is_authenticated:
            return None
        user_id = current_user.id

    member = PodcastMember.query.filter_by(
        podcast_id=podcast_id,
        user_id=user_id
    ).first()

    return member.role if member else None


def user_has_podcast_access(podcast_id, user_id=None):
    """Check if user has any access to a podcast (admin or contributor).

    Args:
        podcast_id: ID of the podcast to check.
        user_id: User ID to check. Defaults to current_user.id.

    Returns:
        True if user has access, False otherwise.
    """
    role = get_user_role(podcast_id, user_id)
    return role is not None


def user_is_podcast_admin(podcast_id, user_id=None):
    """Check if user has admin role on a podcast.

    Args:
        podcast_id: ID of the podcast to check.
        user_id: User ID to check. Defaults to current_user.id.

    Returns:
        True if user is admin, False otherwise.
    """
    role = get_user_role(podcast_id, user_id)
    return role == 'admin'


def get_podcast_or_404(podcast_id):
    """Get a podcast by ID, raising 404 if not found.

    Args:
        podcast_id: ID of the podcast.

    Returns:
        Podcast object.

    Raises:
        404 if podcast not found.
    """
    from models import Podcast
    return Podcast.query.get_or_404(podcast_id)


def require_podcast_access(f):
    """Decorator that requires user to have any access to a podcast.

    The decorated function must have 'podcast_id' as a parameter.
    Returns 403 if user doesn't have access.
    Sets g.podcast and g.user_podcast_role for use in the view.

    Usage:
        @bp.route('/podcasts/<int:podcast_id>/episodes')
        @login_required
        @require_podcast_access
        def list_episodes(podcast_id):
            # g.podcast and g.user_podcast_role are available
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        podcast_id = kwargs.get('podcast_id')
        if podcast_id is None:
            abort(400, description="podcast_id is required")

        # Check access
        role = get_user_role(podcast_id)
        if role is None:
            flash('You do not have access to this podcast.', 'error')
            return redirect(url_for('podcasts.list_podcasts'))

        # Get podcast and store in g
        podcast = get_podcast_or_404(podcast_id)
        g.podcast = podcast
        g.user_podcast_role = role

        return f(*args, **kwargs)
    return decorated_function


def require_podcast_admin(f):
    """Decorator that requires user to have admin role on a podcast.

    The decorated function must have 'podcast_id' as a parameter.
    Returns 403 if user is not admin.
    Sets g.podcast and g.user_podcast_role for use in the view.

    Usage:
        @bp.route('/podcasts/<int:podcast_id>/settings')
        @login_required
        @require_podcast_admin
        def podcast_settings(podcast_id):
            # User is confirmed admin, g.podcast available
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        podcast_id = kwargs.get('podcast_id')
        if podcast_id is None:
            abort(400, description="podcast_id is required")

        # Check admin access
        role = get_user_role(podcast_id)
        if role != 'admin':
            if role is None:
                flash('You do not have access to this podcast.', 'error')
            else:
                flash('You need admin access to perform this action.', 'error')
            return redirect(url_for('podcasts.view_podcast', podcast_id=podcast_id))

        # Get podcast and store in g
        podcast = get_podcast_or_404(podcast_id)
        g.podcast = podcast
        g.user_podcast_role = role

        return f(*args, **kwargs)
    return decorated_function


def add_podcast_member(podcast_id, user_id, role='contributor', added_by=None):
    """Add a user as a member of a podcast.

    Args:
        podcast_id: ID of the podcast.
        user_id: ID of the user to add.
        role: 'admin' or 'contributor'. Defaults to 'contributor'.
        added_by: ID of user adding the member. Defaults to current_user.id.

    Returns:
        PodcastMember object if successful, None if user already a member.

    Raises:
        ValueError if role is invalid.
    """
    from models import PodcastMember
    from extensions import db

    if role not in ('admin', 'contributor'):
        raise ValueError(f"Invalid role: {role}. Must be 'admin' or 'contributor'.")

    if added_by is None and current_user.is_authenticated:
        added_by = current_user.id

    # Check if already a member
    existing = PodcastMember.query.filter_by(
        podcast_id=podcast_id,
        user_id=user_id
    ).first()

    if existing:
        return None

    member = PodcastMember(
        podcast_id=podcast_id,
        user_id=user_id,
        role=role,
        added_by=added_by
    )
    db.session.add(member)
    return member


def update_member_role(podcast_id, user_id, new_role):
    """Update a member's role on a podcast.

    Args:
        podcast_id: ID of the podcast.
        user_id: ID of the user.
        new_role: 'admin' or 'contributor'.

    Returns:
        Updated PodcastMember or None if not found.

    Raises:
        ValueError if role is invalid or if this would remove the last admin.
    """
    from models import PodcastMember

    if new_role not in ('admin', 'contributor'):
        raise ValueError(f"Invalid role: {new_role}. Must be 'admin' or 'contributor'.")

    member = PodcastMember.query.filter_by(
        podcast_id=podcast_id,
        user_id=user_id
    ).first()

    if not member:
        return None

    # Check if this would remove the last admin
    if member.role == 'admin' and new_role != 'admin':
        admin_count = PodcastMember.query.filter_by(
            podcast_id=podcast_id,
            role='admin'
        ).count()
        if admin_count <= 1:
            raise ValueError("Cannot remove the last admin. Assign another admin first.")

    member.role = new_role
    return member


def remove_podcast_member(podcast_id, user_id):
    """Remove a user from a podcast.

    Args:
        podcast_id: ID of the podcast.
        user_id: ID of the user to remove.

    Returns:
        True if removed, False if not found.

    Raises:
        ValueError if this would remove the last admin.
    """
    from models import PodcastMember
    from extensions import db

    member = PodcastMember.query.filter_by(
        podcast_id=podcast_id,
        user_id=user_id
    ).first()

    if not member:
        return False

    # Check if this would remove the last admin
    if member.role == 'admin':
        admin_count = PodcastMember.query.filter_by(
            podcast_id=podcast_id,
            role='admin'
        ).count()
        if admin_count <= 1:
            raise ValueError("Cannot remove the last admin. Assign another admin first.")

    db.session.delete(member)
    return True


def can_delete_podcast(podcast_id, user_id=None):
    """Check if a user can delete a podcast.

    Only admins can delete podcasts.

    Args:
        podcast_id: ID of the podcast.
        user_id: User ID to check. Defaults to current_user.id.

    Returns:
        True if user can delete, False otherwise.
    """
    return user_is_podcast_admin(podcast_id, user_id)
