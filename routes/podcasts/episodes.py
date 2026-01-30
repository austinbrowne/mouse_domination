"""Episode CRUD routes: list, create, view, edit, delete, live mode."""
from datetime import date
from flask import render_template, request, redirect, url_for, flash, g, current_app
from flask_login import login_required
from sqlalchemy import or_, exists
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from extensions import db
from models import EpisodeGuide, EpisodeGuideItem, EpisodeGuideTemplate
from constants import (
    EPISODE_GUIDE_SECTIONS, EPISODE_GUIDE_SECTION_NAMES,
    EPISODE_GUIDE_SECTION_PARENTS, EPISODE_GUIDE_STATUS_CHOICES,
    DEFAULT_PAGE_SIZE
)
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.podcast_access import require_podcast_access, require_podcast_admin

from . import podcast_bp


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
            user_role=g.user_podcast_role,
        )

    today = date.today()
    upcoming_episode = podcast.episodes.filter(
        EpisodeGuide.scheduled_date >= today,
        EpisodeGuide.status != 'completed'
    ).order_by(EpisodeGuide.scheduled_date.asc()).first()

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
        # Simplified: just needs active integration with scan_emoji configured
        discord_enabled = integration.is_active and bool(integration.scan_emoji)

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

    custom_sections_json = guide.custom_sections or []

    return render_template('podcasts/episodes/live.html',
        podcast=podcast,
        guide=guide,
        sections=sections,
        section_names=EPISODE_GUIDE_SECTION_NAMES,
        section_parents=EPISODE_GUIDE_SECTION_PARENTS,
        items_json=items_json,
        custom_sections_json=custom_sections_json,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/copy', methods=['POST'])
@login_required
@require_podcast_access
def copy_episode(podcast_id, episode_id):
    """Create new episode by copying items from an existing episode."""
    source = EpisodeGuide.query.options(
        joinedload(EpisodeGuide.items)
    ).filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        guide = EpisodeGuide(
            title=f"Copy of {source.title}",
            episode_number=(source.episode_number or 0) + 1 if source.episode_number else None,
            podcast_id=podcast_id,
            template_id=source.template_id,
            status='draft',
        )
        db.session.add(guide)
        db.session.flush()

        for item in source.items:
            new_item = EpisodeGuideItem(
                guide_id=guide.id,
                section=item.section,
                title=item.title,
                links=item.all_links.copy() if item.all_links else None,
                notes=item.notes,
                position=item.position,
                timestamp_seconds=None,
                discussed=False,
            )
            db.session.add(new_item)

        db.session.commit()
        flash(f'Episode copied as "{guide.title}".', 'success')
        return redirect(url_for('podcasts.edit_episode', podcast_id=podcast_id, episode_id=guide.id))

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Copy episode', e)
        flash('Database error occurred. Please try again.', 'error')
        return redirect(url_for('podcasts.list_episodes', podcast_id=podcast_id))


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/reopen', methods=['POST'])
@login_required
@require_podcast_access
def reopen_episode(podcast_id, episode_id):
    """Reopen a completed episode guide as a draft for further editing."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        guide.status = 'draft'
        db.session.commit()
        flash(f'Episode "{guide.title}" reopened as draft.', 'success')
        return redirect(url_for('podcasts.edit_episode', podcast_id=podcast_id, episode_id=episode_id))

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Reopen episode', e)
        flash('Database error occurred. Please try again.', 'error')
        return redirect(url_for('podcasts.view_episode', podcast_id=podcast_id, episode_id=episode_id))
