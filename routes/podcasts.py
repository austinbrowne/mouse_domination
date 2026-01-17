"""Podcast management and scoped episode/template routes.

This module provides:
- Podcast CRUD (list, create, edit, settings)
- Member management (add, remove, change roles)
- Scoped episode and template routes under /podcasts/<id>/
"""
import re
from datetime import datetime, timezone, date
from flask_login import login_required, current_user
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g, current_app, abort
from sqlalchemy import or_, exists
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
from models import (
    Podcast, PodcastMember, User,
    EpisodeGuide, EpisodeGuideItem, EpisodeGuideTemplate,
    DiscordIntegration, DiscordEmojiMapping, DiscordImportLog
)
from extensions import db
from constants import (
    EPISODE_GUIDE_SECTIONS, EPISODE_GUIDE_SECTION_CHOICES,
    EPISODE_GUIDE_SECTION_NAMES, EPISODE_GUIDE_SECTION_PARENTS,
    EPISODE_GUIDE_STATUS_CHOICES, DEFAULT_PAGE_SIZE,
    INTRO_STATIC_CONTENT, OUTRO_STATIC_CONTENT
)
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.podcast_access import (
    get_user_podcasts, get_user_role, user_has_podcast_access, user_is_podcast_admin,
    require_podcast_access, require_podcast_admin, add_podcast_member,
    update_member_role, remove_podcast_member
)

podcast_bp = Blueprint('podcasts', __name__)


# =============================================================================
# Helper Functions
# =============================================================================

def generate_unique_slug(name, exclude_id=None):
    """Generate a unique slug from podcast name.

    Args:
        name: Podcast name to convert.
        exclude_id: Podcast ID to exclude from uniqueness check (for editing).

    Returns:
        Unique slug string.
    """
    # Convert name to slug
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')

    if not slug:
        slug = 'podcast'

    # Check for uniqueness
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


def get_sections_with_items(guide):
    """Organize guide items by section for template rendering."""
    sections = {}

    if guide:
        all_sections = guide.get_all_sections()
    else:
        all_sections = EPISODE_GUIDE_SECTIONS

    for key, name, parent in all_sections:
        sections[key] = {
            'key': key,
            'name': name,
            'parent': parent,
            'items': []
        }

    if guide and guide.items:
        for item in guide.items:
            if item.section in sections:
                sections[item.section]['items'].append(item)

    return sections


# =============================================================================
# Podcast List and Create
# =============================================================================

@podcast_bp.route('/')
@login_required
def list_podcasts():
    """List all podcasts the user has access to."""
    podcasts = get_user_podcasts()

    # Get user's role for each podcast for display
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

            # Generate unique slug
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
            db.session.flush()  # Get the ID

            # Add creator as admin
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


# =============================================================================
# Podcast Dashboard and Settings
# =============================================================================

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

            # Check if user wants to update the slug
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
        db.session.delete(podcast)  # Cascade will delete members, episodes, templates
        db.session.commit()
        flash(f'Podcast "{name}" deleted.', 'success')
        return redirect(url_for('podcasts.list_podcasts'))
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete podcast', e)
        flash('Database error occurred. Please try again.', 'error')
        return redirect(url_for('podcasts.view_podcast', podcast_id=podcast_id))


# =============================================================================
# Member Management
# =============================================================================

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

    # Get list of users who can be added (approved users not already members)
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

        # Verify user exists and is approved
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


# =============================================================================
# Episode Routes (scoped under podcast)
# =============================================================================

@podcast_bp.route('/<int:podcast_id>/episodes/')
@login_required
@require_podcast_access
def list_episodes(podcast_id):
    """List all episodes for a podcast."""
    podcast = g.podcast

    status = request.args.get('status')
    search = request.args.get('search', '').strip()[:100]
    page = request.args.get('page', 1, type=int)

    query = EpisodeGuide.query.filter_by(podcast_id=podcast_id)

    if status and status in EPISODE_GUIDE_STATUS_CHOICES:
        query = query.filter_by(status=status)

    if search:
        search_term = f"%{search}%"
        guide_conditions = or_(
            EpisodeGuide.title.ilike(search_term),
            EpisodeGuide.notes.ilike(search_term),
            EpisodeGuide.previous_poll.ilike(search_term),
            EpisodeGuide.new_poll.ilike(search_term),
        )
        item_exists = exists().where(
            EpisodeGuideItem.guide_id == EpisodeGuide.id,
            or_(
                EpisodeGuideItem.title.ilike(search_term),
                EpisodeGuideItem.link.ilike(search_term),
                EpisodeGuideItem.links.cast(db.String).ilike(search_term),
                EpisodeGuideItem.notes.ilike(search_term),
            )
        )
        query = query.filter(or_(guide_conditions, item_exists))

    pagination = query.order_by(EpisodeGuide.created_at.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Find matching items for display (only when searching)
    matching_items = {}
    if search:
        search_term = f"%{search}%"
        guide_ids = [g.id for g in pagination.items]
        if guide_ids:
            items = EpisodeGuideItem.query.filter(
                EpisodeGuideItem.guide_id.in_(guide_ids),
                or_(
                    EpisodeGuideItem.title.ilike(search_term),
                    EpisodeGuideItem.link.ilike(search_term),
                    EpisodeGuideItem.links.cast(db.String).ilike(search_term),
                    EpisodeGuideItem.notes.ilike(search_term),
                )
            ).all()
            for item in items:
                matching_items.setdefault(item.guide_id, []).append(item)

    # Stats for this podcast
    total = podcast.episodes.count()
    drafts = podcast.episodes.filter_by(status='draft').count()
    completed = podcast.episodes.filter_by(status='completed').count()
    stats = {'total': total, 'drafts': drafts, 'completed': completed}

    if request.args.get('ajax') == '1':
        return render_template('podcasts/episodes/_table.html',
            podcast=podcast,
            guides=pagination.items,
            search=search,
            matching_items=matching_items,
            stats=stats,
        )

    # Next upcoming episode (scheduled_date >= today, not completed)
    today = date.today()
    upcoming_episode = podcast.episodes.filter(
        EpisodeGuide.scheduled_date >= today,
        EpisodeGuide.status != 'completed'
    ).order_by(EpisodeGuide.scheduled_date.asc()).first()

    # Get items for upcoming episode grouped by section
    upcoming_items_by_section = {}
    upcoming_sections = []
    if upcoming_episode:
        upcoming_sections = upcoming_episode.get_all_sections()
        items = EpisodeGuideItem.query.filter_by(guide_id=upcoming_episode.id).order_by(
            EpisodeGuideItem.section, EpisodeGuideItem.position
        ).all()
        for item in items:
            if item.section not in upcoming_items_by_section:
                upcoming_items_by_section[item.section] = []
            upcoming_items_by_section[item.section].append(item)

    return render_template('podcasts/episodes/list.html',
        podcast=podcast,
        guides=pagination.items,
        pagination=pagination,
        current_status=status,
        search=search,
        matching_items=matching_items,
        stats=stats,
        user_role=g.user_podcast_role,
        upcoming_episode=upcoming_episode,
        upcoming_sections=upcoming_sections,
        upcoming_items_by_section=upcoming_items_by_section,
    )


@podcast_bp.route('/<int:podcast_id>/episodes/new', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def new_episode(podcast_id):
    """Create a new episode for a podcast."""
    podcast = g.podcast

    # Get templates for this podcast
    templates = EpisodeGuideTemplate.query.filter_by(
        podcast_id=podcast_id
    ).order_by(
        EpisodeGuideTemplate.is_default.desc(),
        EpisodeGuideTemplate.name
    ).all()

    if request.method == 'POST':
        try:
            form = FormData(request.form)
            episode_number = form.integer('episode_number')

            # Auto-populate previous_poll from last episode if exists
            previous_poll = None
            previous_poll_link = None
            if episode_number:
                prev_guide = EpisodeGuide.query.filter(
                    EpisodeGuide.podcast_id == podcast_id,
                    EpisodeGuide.episode_number == episode_number - 1
                ).first()
                if prev_guide and prev_guide.new_poll:
                    previous_poll = prev_guide.new_poll
                    previous_poll_link = prev_guide.new_poll_link

            template_id = form.integer('template_id')
            template = None
            if template_id:
                template = EpisodeGuideTemplate.query.filter_by(
                    id=template_id,
                    podcast_id=podcast_id
                ).first()

            guide = EpisodeGuide(
                podcast_id=podcast_id,
                title=form.required('title'),
                episode_number=episode_number,
                scheduled_date=form.date('scheduled_date'),
                notes=form.optional('notes'),
                previous_poll=previous_poll,
                previous_poll_link=previous_poll_link,
                status='draft',
                template_id=template_id if template else None,
            )

            # Apply template defaults if selected
            if template:
                guide.intro_static_content = template.intro_static_content
                guide.outro_static_content = template.outro_static_content
                guide.custom_sections = template.default_sections
                if template.default_poll_1:
                    guide.new_poll = template.default_poll_1

            db.session.add(guide)
            db.session.commit()
            flash(f'Episode guide "{guide.title}" created.', 'success')
            return redirect(url_for('podcasts.edit_episode', podcast_id=podcast_id, episode_id=guide.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Create episode', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('podcasts/episodes/form.html',
        podcast=podcast,
        guide=None,
        templates=templates,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/')
@login_required
@require_podcast_access
def view_episode(podcast_id, episode_id):
    """View a completed episode guide with timestamps."""
    podcast = g.podcast
    guide = EpisodeGuide.query.options(
        joinedload(EpisodeGuide.items)
    ).filter_by(id=episode_id, podcast_id=podcast_id).first_or_404()

    sections = get_sections_with_items(guide)

    return render_template('podcasts/episodes/view.html',
        podcast=podcast,
        guide=guide,
        sections=sections,
        section_names=EPISODE_GUIDE_SECTION_NAMES,
        section_parents=EPISODE_GUIDE_SECTION_PARENTS,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/edit', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def edit_episode(podcast_id, episode_id):
    """Edit episode guide metadata and items."""
    podcast = g.podcast
    guide = EpisodeGuide.query.options(
        joinedload(EpisodeGuide.items)
    ).filter_by(id=episode_id, podcast_id=podcast_id).first_or_404()

    if request.method == 'POST':
        try:
            form = FormData(request.form)
            guide.title = form.required('title')
            guide.episode_number = form.integer('episode_number')
            guide.scheduled_date = form.date('scheduled_date')
            guide.notes = form.optional('notes')

            db.session.commit()
            flash('Episode guide updated.', 'success')
            return redirect(url_for('podcasts.edit_episode', podcast_id=podcast_id, episode_id=episode_id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Update episode', e)
            flash('Database error occurred. Please try again.', 'error')

    sections = get_sections_with_items(guide)
    items_json = [item.to_dict() for item in guide.items] if guide.items else []

    discord_enabled = False
    if g.user_podcast_role == 'admin' and guide.template and guide.template.discord_integration:
        integration = guide.template.discord_integration
        discord_enabled = integration.is_active and len(integration.emoji_mappings) > 0

    return render_template('podcasts/episodes/edit.html',
        podcast=podcast,
        guide=guide,
        sections=sections,
        section_names=EPISODE_GUIDE_SECTION_NAMES,
        section_parents=EPISODE_GUIDE_SECTION_PARENTS,
        all_sections=EPISODE_GUIDE_SECTIONS,
        items_json=items_json,
        discord_enabled=discord_enabled,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/delete', methods=['POST'])
@login_required
@require_podcast_admin
def delete_episode(podcast_id, episode_id):
    """Delete an episode guide."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        title = guide.title
        db.session.delete(guide)
        db.session.commit()
        flash(f'Episode guide "{title}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete episode', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('podcasts.list_episodes', podcast_id=podcast_id))


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/live')
@login_required
@require_podcast_access
def live_episode(podcast_id, episode_id):
    """Live recording mode for an episode."""
    podcast = g.podcast
    guide = EpisodeGuide.query.options(
        joinedload(EpisodeGuide.items)
    ).filter_by(id=episode_id, podcast_id=podcast_id).first_or_404()

    sections = get_sections_with_items(guide)
    items_json = [item.to_dict() for item in guide.items] if guide.items else []

    return render_template('podcasts/episodes/live.html',
        podcast=podcast,
        guide=guide,
        sections=sections,
        section_names=EPISODE_GUIDE_SECTION_NAMES,
        section_parents=EPISODE_GUIDE_SECTION_PARENTS,
        items_json=items_json,
        user_role=g.user_podcast_role,
    )


# =============================================================================
# Episode AJAX endpoints
# =============================================================================

@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/metadata', methods=['PUT'])
@login_required
@require_podcast_access
def update_episode_metadata(podcast_id, episode_id):
    """Update episode metadata via AJAX."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400

        if 'title' in data:
            title = data['title'].strip() if data['title'] else ''
            if not title:
                return jsonify({'success': False, 'error': 'Title is required'}), 400
            guide.title = title

        if 'episode_number' in data:
            guide.episode_number = int(data['episode_number']) if data['episode_number'] else None

        if 'previous_poll' in data:
            guide.previous_poll = data['previous_poll'].strip() if data['previous_poll'] else None

        if 'previous_poll_link' in data:
            guide.previous_poll_link = data['previous_poll_link'].strip() if data['previous_poll_link'] else None

        if 'new_poll' in data:
            guide.new_poll = data['new_poll'].strip() if data['new_poll'] else None

        if 'new_poll_link' in data:
            guide.new_poll_link = data['new_poll_link'].strip() if data['new_poll_link'] else None

        db.session.commit()
        return jsonify({'success': True, 'guide': guide.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Update episode metadata', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/items', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def episode_items(podcast_id, episode_id):
    """Get or create items for an episode."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    if request.method == 'GET':
        items = EpisodeGuideItem.query.filter_by(guide_id=episode_id).order_by(
            EpisodeGuideItem.section,
            EpisodeGuideItem.position
        ).all()
        return jsonify({'success': True, 'items': [item.to_dict() for item in items]})

    # POST - create new item
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400

        section = data.get('section', 'introduction')
        title = (data.get('title') or '').strip()

        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        valid_sections = [s[0] for s in guide.get_all_sections()]
        if section not in valid_sections:
            return jsonify({'success': False, 'error': 'Invalid section'}), 400

        max_pos = db.session.query(db.func.max(EpisodeGuideItem.position)).filter_by(
            guide_id=episode_id,
            section=section
        ).scalar() or 0

        # Handle links (support both 'links' array and legacy 'link' single value)
        links = data.get('links') or []
        single_link = (data.get('link') or '').strip()
        if single_link and not links:
            links = [single_link]
        # Filter empty strings and strip whitespace
        links = [l.strip() for l in links if l and l.strip()] or None

        item = EpisodeGuideItem(
            guide_id=episode_id,
            section=section,
            title=title,
            links=links,
            notes=(data.get('notes') or '').strip() or None,
            position=max_pos + 1,
        )
        db.session.add(item)
        db.session.commit()

        return jsonify({'success': True, 'item': item.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Create episode item', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/items/<int:item_id>', methods=['PUT', 'DELETE'])
@login_required
@require_podcast_access
def episode_item(podcast_id, episode_id, item_id):
    """Update or delete an episode item."""
    # Verify episode belongs to podcast
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    item = EpisodeGuideItem.query.filter_by(
        id=item_id,
        guide_id=episode_id
    ).first_or_404()

    if request.method == 'DELETE':
        try:
            db.session.delete(item)
            db.session.commit()
            return jsonify({'success': True})
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Delete episode item', e)
            return jsonify({'success': False, 'error': 'Database error'}), 500

    # PUT - update item
    try:
        data = request.get_json()

        if 'title' in data:
            title = data['title'].strip() if data['title'] else ''
            if not title:
                return jsonify({'success': False, 'error': 'Title is required'}), 400
            item.title = title

        if 'links' in data:
            links = data['links']
            if isinstance(links, str):
                links = [links] if links.strip() else []
            item.links = links if links else None

        if 'notes' in data:
            item.notes = data['notes'].strip() if data['notes'] else None

        if 'section' in data:
            valid_sections = [s[0] for s in guide.get_all_sections()]
            if data['section'] in valid_sections:
                item.section = data['section']

        if 'position' in data:
            item.position = int(data['position'])

        if 'discussed' in data:
            item.discussed = bool(data['discussed'])

        if 'timestamp_seconds' in data:
            item.timestamp_seconds = int(data['timestamp_seconds']) if data['timestamp_seconds'] else None

        db.session.commit()
        return jsonify({'success': True, 'item': item.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Update episode item', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/recording', methods=['POST'])
@login_required
@require_podcast_access
def toggle_recording(podcast_id, episode_id):
    """Toggle recording state for an episode."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
        action = data.get('action')

        if action == 'start':
            guide.status = 'recording'
            guide.recording_started_at = datetime.now(timezone.utc)
            guide.recording_ended_at = None
            guide.total_duration_seconds = None

        elif action == 'stop':
            guide.status = 'completed'
            guide.recording_ended_at = datetime.now(timezone.utc)
            if guide.recording_started_at:
                # Handle timezone-naive datetimes from SQLite
                started = guide.recording_started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                delta = guide.recording_ended_at - started
                guide.total_duration_seconds = int(delta.total_seconds())

        elif action == 'reset':
            guide.status = 'draft'
            guide.recording_started_at = None
            guide.recording_ended_at = None
            guide.total_duration_seconds = None
            # Reset all item timestamps
            for item in guide.items:
                item.timestamp_seconds = None
                item.discussed = False

        db.session.commit()
        return jsonify({'success': True, 'guide': guide.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Toggle recording', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


# =============================================================================
# Template Routes (scoped under podcast)
# =============================================================================

@podcast_bp.route('/<int:podcast_id>/templates/')
@login_required
@require_podcast_access
def list_templates(podcast_id):
    """List all templates for a podcast."""
    podcast = g.podcast

    templates = EpisodeGuideTemplate.query.filter_by(
        podcast_id=podcast_id
    ).order_by(
        EpisodeGuideTemplate.is_default.desc(),
        EpisodeGuideTemplate.name
    ).all()

    return render_template('podcasts/templates/list.html',
        podcast=podcast,
        templates=templates,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/templates/new', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def new_template(podcast_id):
    """Create a new template for a podcast."""
    podcast = g.podcast

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            template = EpisodeGuideTemplate(
                podcast_id=podcast_id,
                name=form.required('name', max_length=100),
                description=form.optional('description'),
                default_poll_1=form.optional('default_poll_1'),
                default_poll_2=form.optional('default_poll_2'),
                created_by=current_user.id,
                is_default=form.boolean('is_default'),
            )

            # Process intro/outro content
            intro_content = request.form.getlist('intro_static_content[]')
            intro_content = [line.strip() for line in intro_content if line.strip()]
            template.intro_static_content = intro_content if intro_content else None

            outro_content = request.form.getlist('outro_static_content[]')
            outro_content = [line.strip() for line in outro_content if line.strip()]
            template.outro_static_content = outro_content if outro_content else None

            # If this is default, unset others
            if template.is_default:
                EpisodeGuideTemplate.query.filter(
                    EpisodeGuideTemplate.podcast_id == podcast_id,
                    EpisodeGuideTemplate.is_default == True
                ).update({'is_default': False})

            db.session.add(template)
            db.session.commit()
            flash(f'Template "{template.name}" created.', 'success')
            return redirect(url_for('podcasts.edit_template', podcast_id=podcast_id, template_id=template.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Create template', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('podcasts/templates/form.html',
        podcast=podcast,
        template=None,
        intro_content=INTRO_STATIC_CONTENT,
        outro_content=OUTRO_STATIC_CONTENT,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def edit_template(podcast_id, template_id):
    """Edit a template."""
    podcast = g.podcast
    template = EpisodeGuideTemplate.query.filter_by(
        id=template_id,
        podcast_id=podcast_id
    ).first_or_404()

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            template.name = form.required('name', max_length=100)
            template.description = form.optional('description')
            template.default_poll_1 = form.optional('default_poll_1')
            template.default_poll_2 = form.optional('default_poll_2')
            template.is_default = form.boolean('is_default')

            # Process intro/outro content
            intro_content = request.form.getlist('intro_static_content[]')
            intro_content = [line.strip() for line in intro_content if line.strip()]
            template.intro_static_content = intro_content if intro_content else None

            outro_content = request.form.getlist('outro_static_content[]')
            outro_content = [line.strip() for line in outro_content if line.strip()]
            template.outro_static_content = outro_content if outro_content else None

            # If this is default, unset others
            if template.is_default:
                EpisodeGuideTemplate.query.filter(
                    EpisodeGuideTemplate.podcast_id == podcast_id,
                    EpisodeGuideTemplate.id != template.id,
                    EpisodeGuideTemplate.is_default == True
                ).update({'is_default': False})

            db.session.commit()
            flash('Template updated.', 'success')
            return redirect(url_for('podcasts.edit_template', podcast_id=podcast_id, template_id=template_id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Update template', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('podcasts/templates/form.html',
        podcast=podcast,
        template=template,
        intro_content=template.intro_static_content or INTRO_STATIC_CONTENT,
        outro_content=template.outro_static_content or OUTRO_STATIC_CONTENT,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/delete', methods=['POST'])
@login_required
@require_podcast_admin
def delete_template(podcast_id, template_id):
    """Delete a template."""
    template = EpisodeGuideTemplate.query.filter_by(
        id=template_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        name = template.name
        db.session.delete(template)
        db.session.commit()
        flash(f'Template "{name}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete template', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('podcasts.list_templates', podcast_id=podcast_id))
