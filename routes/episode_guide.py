from datetime import datetime, timezone
from flask_login import login_required
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError
from models import EpisodeGuide, EpisodeGuideItem
from extensions import db
from constants import (
    EPISODE_GUIDE_SECTIONS, EPISODE_GUIDE_SECTION_CHOICES,
    EPISODE_GUIDE_SECTION_NAMES, EPISODE_GUIDE_SECTION_PARENTS,
    EPISODE_GUIDE_STATUS_CHOICES, DEFAULT_PAGE_SIZE
)
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception

episode_guide_bp = Blueprint('episode_guide', __name__)


def get_sections_with_items(guide):
    """Organize guide items by section for template rendering."""
    sections = {}
    for key, name, parent in EPISODE_GUIDE_SECTIONS:
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


@episode_guide_bp.route('/')
@login_required
def list_guides():
    """List all episode guides with filtering by status."""
    status = request.args.get('status')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = EpisodeGuide.query

    if status and status in EPISODE_GUIDE_STATUS_CHOICES:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(EpisodeGuide.title.ilike(f"%{search}%"))

    pagination = query.order_by(EpisodeGuide.created_at.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Stats
    total = EpisodeGuide.query.count()
    drafts = EpisodeGuide.query.filter_by(status='draft').count()
    completed = EpisodeGuide.query.filter_by(status='completed').count()

    return render_template('episode_guide/list.html',
        guides=pagination.items,
        pagination=pagination,
        current_status=status,
        search=search,
        stats={'total': total, 'drafts': drafts, 'completed': completed},
    )


@episode_guide_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_guide():
    """Create a new episode guide."""
    if request.method == 'POST':
        try:
            form = FormData(request.form)

            episode_number = form.integer('episode_number')

            # Auto-populate previous_poll from last episode if exists
            previous_poll = None
            previous_poll_link = None
            if episode_number:
                prev_guide = EpisodeGuide.query.filter(
                    EpisodeGuide.episode_number == episode_number - 1
                ).first()
                if prev_guide and prev_guide.new_poll:
                    previous_poll = prev_guide.new_poll
                    previous_poll_link = prev_guide.new_poll_link

            guide = EpisodeGuide(
                title=form.required('title'),
                episode_number=episode_number,
                notes=form.optional('notes'),
                previous_poll=previous_poll,
                previous_poll_link=previous_poll_link,
                status='draft',
            )

            db.session.add(guide)
            db.session.commit()
            flash(f'Episode guide "{guide.title}" created.', 'success')
            return redirect(url_for('episode_guide.edit_guide', id=guide.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('episode_guide/form.html', guide=None)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('episode_guide/form.html', guide=None)

    return render_template('episode_guide/form.html', guide=None)


@episode_guide_bp.route('/new-from/<int:source_id>', methods=['POST'])
@login_required
def copy_guide(source_id):
    """Create new guide by copying items from previous episode."""
    try:
        source = EpisodeGuide.query.get_or_404(source_id)

        # Create new guide
        guide = EpisodeGuide(
            title=f"Copy of {source.title}",
            episode_number=(source.episode_number or 0) + 1 if source.episode_number else None,
            status='draft',
        )
        db.session.add(guide)
        db.session.flush()  # Get the ID

        # Copy items (reset timestamps)
        for item in source.items:
            new_item = EpisodeGuideItem(
                guide_id=guide.id,
                section=item.section,
                title=item.title,
                link=item.link,
                notes=item.notes,
                position=item.position,
                timestamp_seconds=None,
                discussed=False,
            )
            db.session.add(new_item)

        db.session.commit()
        flash(f'Episode guide copied as "{guide.title}".', 'success')
        return redirect(url_for('episode_guide.edit_guide', id=guide.id))

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
        return redirect(url_for('episode_guide.list_guides'))


@episode_guide_bp.route('/<int:id>')
@login_required
def view_guide(id):
    """View a completed episode guide with timestamps."""
    guide = EpisodeGuide.query.get_or_404(id)
    sections = get_sections_with_items(guide)

    return render_template('episode_guide/view.html',
        guide=guide,
        sections=sections,
        section_names=EPISODE_GUIDE_SECTION_NAMES,
        section_parents=EPISODE_GUIDE_SECTION_PARENTS,
    )


@episode_guide_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_guide(id):
    """Edit episode guide metadata and items."""
    guide = EpisodeGuide.query.get_or_404(id)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            guide.title = form.required('title')
            guide.episode_number = form.integer('episode_number')
            guide.notes = form.optional('notes')

            db.session.commit()
            flash('Episode guide updated.', 'success')
            return redirect(url_for('episode_guide.edit_guide', id=guide.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')

    sections = get_sections_with_items(guide)

    # Pre-serialize items for JavaScript (to_dict is a method, not attribute)
    items_json = [item.to_dict() for item in guide.items] if guide.items else []

    return render_template('episode_guide/edit.html',
        guide=guide,
        sections=sections,
        section_names=EPISODE_GUIDE_SECTION_NAMES,
        section_parents=EPISODE_GUIDE_SECTION_PARENTS,
        all_sections=EPISODE_GUIDE_SECTIONS,
        items_json=items_json,
    )


@episode_guide_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_guide(id):
    """Delete an episode guide."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)
        title = guide.title
        db.session.delete(guide)
        db.session.commit()
        flash(f'Episode guide "{title}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('episode_guide.list_guides'))


# ---- AJAX Endpoints for Guide Metadata ----

@episode_guide_bp.route('/<int:id>/metadata', methods=['PUT'])
@login_required
def update_metadata(id):
    """Update guide metadata (title, episode_number, polls) via AJAX."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)
        data = request.get_json()

        if 'title' in data:
            title = data['title'].strip() if data['title'] else ''
            if not title:
                return jsonify({'success': False, 'error': 'Title is required'}), 400
            guide.title = title

        if 'episode_number' in data:
            new_episode_num = int(data['episode_number']) if data['episode_number'] else None

            # Auto-populate previous_poll from last episode if episode number changed and previous_poll is empty
            if new_episode_num and new_episode_num != guide.episode_number and not guide.previous_poll:
                prev_guide = EpisodeGuide.query.filter(
                    EpisodeGuide.episode_number == new_episode_num - 1
                ).first()
                if prev_guide and prev_guide.new_poll:
                    guide.previous_poll = prev_guide.new_poll
                    guide.previous_poll_link = prev_guide.new_poll_link

            guide.episode_number = new_episode_num

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
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ---- AJAX Endpoints for Item Management ----

@episode_guide_bp.route('/<int:id>/items', methods=['POST'])
@login_required
def add_item(id):
    """Add new item to a section (AJAX)."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)
        data = request.get_json()

        section = data.get('section')
        if section not in EPISODE_GUIDE_SECTION_CHOICES:
            return jsonify({'success': False, 'error': 'Invalid section'}), 400

        title = data.get('title', '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        # Get max position in section
        max_pos = db.session.query(db.func.max(EpisodeGuideItem.position)).filter_by(
            guide_id=id, section=section
        ).scalar() or -1

        item = EpisodeGuideItem(
            guide_id=id,
            section=section,
            title=title,
            link=(data.get('link') or '').strip() or None,
            notes=(data.get('notes') or '').strip() or None,
            position=max_pos + 1,
        )

        db.session.add(item)
        db.session.commit()

        return jsonify({'success': True, 'item': item.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@episode_guide_bp.route('/<int:id>/items/<int:item_id>', methods=['PUT', 'DELETE'])
@login_required
def update_or_delete_item(id, item_id):
    """Update or delete an item (AJAX)."""
    try:
        item = EpisodeGuideItem.query.filter_by(id=item_id, guide_id=id).first_or_404()

        if request.method == 'DELETE':
            db.session.delete(item)
            db.session.commit()
            return jsonify({'success': True})

        # PUT - Update
        data = request.get_json()

        if 'title' in data:
            title = (data['title'] or '').strip()
            if not title:
                return jsonify({'success': False, 'error': 'Title is required'}), 400
            item.title = title

        if 'link' in data:
            item.link = (data['link'] or '').strip() or None

        if 'notes' in data:
            item.notes = (data['notes'] or '').strip() or None

        if 'discussed' in data:
            item.discussed = bool(data['discussed'])

        if 'position' in data:
            item.position = int(data['position'])

        db.session.commit()
        return jsonify({'success': True, 'item': item.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@episode_guide_bp.route('/<int:id>/items/reorder', methods=['POST'])
@login_required
def reorder_items(id):
    """Reorder items within a section (AJAX)."""
    try:
        data = request.get_json()
        section = data.get('section')
        item_ids = data.get('item_ids', [])

        if section not in EPISODE_GUIDE_SECTION_CHOICES:
            return jsonify({'success': False, 'error': 'Invalid section'}), 400

        # Update positions
        for position, item_id in enumerate(item_ids):
            item = EpisodeGuideItem.query.filter_by(id=item_id, guide_id=id, section=section).first()
            if item:
                item.position = position

        db.session.commit()
        return jsonify({'success': True})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ---- Live Recording Mode ----

@episode_guide_bp.route('/<int:id>/live')
@login_required
def live_mode(id):
    """Live recording interface with timer and timestamp buttons."""
    guide = EpisodeGuide.query.get_or_404(id)
    sections = get_sections_with_items(guide)

    return render_template('episode_guide/live.html',
        guide=guide,
        sections=sections,
        section_names=EPISODE_GUIDE_SECTION_NAMES,
        section_parents=EPISODE_GUIDE_SECTION_PARENTS,
        all_sections=EPISODE_GUIDE_SECTIONS,
    )


@episode_guide_bp.route('/<int:id>/start', methods=['POST'])
@login_required
def start_recording(id):
    """Start the timer / begin recording (AJAX)."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)

        guide.status = 'recording'
        guide.recording_started_at = datetime.now(timezone.utc)
        guide.recording_ended_at = None
        guide.total_duration_seconds = None

        db.session.commit()

        return jsonify({
            'success': True,
            'started_at': guide.recording_started_at.isoformat(),
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@episode_guide_bp.route('/<int:id>/stop', methods=['POST'])
@login_required
def stop_recording(id):
    """Stop the timer / end recording (AJAX)."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)
        data = request.get_json() or {}

        guide.status = 'completed'
        guide.recording_ended_at = datetime.now(timezone.utc)
        guide.total_duration_seconds = data.get('elapsed_seconds', 0)

        db.session.commit()

        return jsonify({
            'success': True,
            'duration': guide.total_duration_seconds,
            'formatted_duration': guide.formatted_duration,
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@episode_guide_bp.route('/<int:id>/reopen', methods=['POST'])
@login_required
def reopen_guide(id):
    """Reopen a completed guide as a draft for further editing."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)

        guide.status = 'draft'
        # Keep the recording data (timestamps, duration) intact

        db.session.commit()
        flash(f'Episode "{guide.title}" reopened as draft.', 'success')
        return redirect(url_for('episode_guide.edit_guide', id=guide.id))

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
        return redirect(url_for('episode_guide.view_guide', id=id))


@episode_guide_bp.route('/<int:id>/timestamp/<int:item_id>', methods=['POST'])
@login_required
def capture_timestamp(id, item_id):
    """Capture current timestamp for an item (AJAX)."""
    try:
        item = EpisodeGuideItem.query.filter_by(id=item_id, guide_id=id).first_or_404()
        data = request.get_json() or {}

        elapsed_seconds = data.get('elapsed_seconds', 0)
        item.timestamp_seconds = int(elapsed_seconds)
        item.discussed = True

        db.session.commit()

        return jsonify({
            'success': True,
            'timestamp_seconds': item.timestamp_seconds,
            'timestamp_formatted': item.formatted_timestamp,
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500
