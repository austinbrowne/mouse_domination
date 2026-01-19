"""Podcast CRUD operations: list, create, settings, delete."""
import re
from flask import render_template, request, redirect, url_for, flash, g, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Podcast, PodcastMember
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.podcast_access import get_user_podcasts, get_user_role, require_podcast_access, require_podcast_admin

from . import podcast_bp


def generate_unique_slug(name, exclude_id=None):
    """Generate a unique slug from podcast name.

    Args:
        name: Podcast name to convert.
        exclude_id: Podcast ID to exclude from uniqueness check (for editing).

    Returns:
        Unique slug string.
    """
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')

    if not slug:
        slug = 'podcast'

    base_slug = slug
    counter = 1

    while True:
        query = Podcast.query.filter_by(slug=slug)
        if exclude_id:
            query = query.filter(Podcast.id != exclude_id)
        if not query.first():
            break
        counter += 1
        slug = f"{base_slug}-{counter}"

    return slug


@podcast_bp.route('/')
@login_required
def list_podcasts():
    """List all podcasts the user has access to."""
    podcasts = get_user_podcasts()

    podcast_roles = {}
    for p in podcasts:
        podcast_roles[p.id] = get_user_role(p.id)

    return render_template('podcasts/list.html',
        podcasts=podcasts,
        podcast_roles=podcast_roles,
    )


@podcast_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_podcast():
    """Create a new podcast. Creator becomes admin."""
    if request.method == 'POST':
        try:
            form = FormData(request.form)
            name = form.required('name', max_length=150)
            description = form.optional('description')
            website_url = form.optional('website_url')
            rss_feed_url = form.optional('rss_feed_url')

            slug = generate_unique_slug(name)

            podcast = Podcast(
                name=name,
                slug=slug,
                description=description,
                website_url=website_url,
                rss_feed_url=rss_feed_url,
                created_by=current_user.id,
                is_active=True,
            )
            db.session.add(podcast)
            db.session.flush()

            member = PodcastMember(
                podcast_id=podcast.id,
                user_id=current_user.id,
                role='admin',
                added_by=current_user.id,
            )
            db.session.add(member)
            db.session.commit()

            flash(f'Podcast "{podcast.name}" created.', 'success')
            return redirect(url_for('podcasts.view_podcast', podcast_id=podcast.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Create podcast', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('podcasts/form.html', podcast=None)


@podcast_bp.route('/<int:podcast_id>/')
@login_required
@require_podcast_access
def view_podcast(podcast_id):
    """Redirect to episodes list (main podcast view)."""
    return redirect(url_for('podcasts.list_episodes', podcast_id=podcast_id))


@podcast_bp.route('/<int:podcast_id>/settings', methods=['GET', 'POST'])
@login_required
@require_podcast_admin
def podcast_settings(podcast_id):
    """Edit podcast settings (admin only)."""
    podcast = g.podcast

    if request.method == 'POST':
        try:
            form = FormData(request.form)
            name = form.required('name', max_length=150)
            description = form.optional('description')
            website_url = form.optional('website_url')
            rss_feed_url = form.optional('rss_feed_url')

            update_slug = form.boolean('update_slug')
            if update_slug:
                podcast.slug = generate_unique_slug(name, exclude_id=podcast.id)

            podcast.name = name
            podcast.description = description
            podcast.website_url = website_url
            podcast.rss_feed_url = rss_feed_url

            db.session.commit()
            flash('Podcast settings updated.', 'success')
            return redirect(url_for('podcasts.podcast_settings', podcast_id=podcast_id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Update podcast settings', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('podcasts/settings.html',
        podcast=podcast,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/delete', methods=['POST'])
@login_required
@require_podcast_admin
def delete_podcast(podcast_id):
    """Delete a podcast and all its episodes/templates (admin only)."""
    podcast = g.podcast

    try:
        name = podcast.name
        db.session.delete(podcast)
        db.session.commit()
        flash(f'Podcast "{name}" deleted.', 'success')
        return redirect(url_for('podcasts.list_podcasts'))
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete podcast', e)
        flash('Database error occurred. Please try again.', 'error')
        return redirect(url_for('podcasts.view_podcast', podcast_id=podcast_id))
