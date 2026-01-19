"""Podcast member management: list, add, change role, remove."""
from flask import render_template, request, redirect, url_for, flash, g, current_app
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from extensions import db
from models import PodcastMember, User
from utils.routes import FormData
from utils.logging import log_exception
from utils.podcast_access import (
    require_podcast_admin, add_podcast_member,
    update_member_role, remove_podcast_member
)

from . import podcast_bp


@podcast_bp.route('/<int:podcast_id>/members')
@login_required
@require_podcast_admin
def list_members(podcast_id):
    """List and manage podcast members (admin only)."""
    podcast = g.podcast

    members = PodcastMember.query.filter_by(
        podcast_id=podcast_id
    ).options(
        joinedload(PodcastMember.user),
        joinedload(PodcastMember.adder)
    ).order_by(PodcastMember.role, PodcastMember.created_at).all()

    member_user_ids = [m.user_id for m in members]
    available_users = User.query.filter(
        User.is_approved == True,
        ~User.id.in_(member_user_ids) if member_user_ids else True
    ).order_by(User.name).all()

    return render_template('podcasts/members.html',
        podcast=podcast,
        members=members,
        available_users=available_users,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/members/add', methods=['POST'])
@login_required
@require_podcast_admin
def add_member(podcast_id):
    """Add a member to the podcast (admin only)."""
    podcast = g.podcast

    try:
        form = FormData(request.form)
        user_id = form.integer('user_id')
        role = form.choice('role', ['admin', 'contributor'], default='contributor')

        user = User.query.get(user_id)
        if not user or not user.is_approved:
            flash('Invalid user selected.', 'error')
            return redirect(url_for('podcasts.list_members', podcast_id=podcast_id))

        member = add_podcast_member(podcast_id, user_id, role)
        if member:
            db.session.commit()
            flash(f'{user.name or user.email} added as {role}.', 'success')
        else:
            flash('User is already a member.', 'error')

    except ValueError as e:
        flash(str(e), 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Add podcast member', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('podcasts.list_members', podcast_id=podcast_id))


@podcast_bp.route('/<int:podcast_id>/members/<int:user_id>/role', methods=['POST'])
@login_required
@require_podcast_admin
def change_member_role(podcast_id, user_id):
    """Change a member's role (admin only)."""
    try:
        form = FormData(request.form)
        new_role = form.choice('role', ['admin', 'contributor'])

        if not new_role:
            flash('Invalid role.', 'error')
            return redirect(url_for('podcasts.list_members', podcast_id=podcast_id))

        member = update_member_role(podcast_id, user_id, new_role)
        if member:
            db.session.commit()
            flash(f'Role changed to {new_role}.', 'success')
        else:
            flash('Member not found.', 'error')

    except ValueError as e:
        flash(str(e), 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Change member role', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('podcasts.list_members', podcast_id=podcast_id))


@podcast_bp.route('/<int:podcast_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
@require_podcast_admin
def remove_member(podcast_id, user_id):
    """Remove a member from the podcast (admin only)."""
    try:
        if remove_podcast_member(podcast_id, user_id):
            db.session.commit()
            flash('Member removed.', 'success')
        else:
            flash('Member not found.', 'error')

    except ValueError as e:
        flash(str(e), 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Remove podcast member', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('podcasts.list_members', podcast_id=podcast_id))
