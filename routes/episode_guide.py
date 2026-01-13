from datetime import datetime, timezone
from flask_login import login_required, current_user
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from sqlalchemy import or_, exists
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from models import EpisodeGuide, EpisodeGuideItem, EpisodeGuideTemplate
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

episode_guide_bp = Blueprint('episode_guide', __name__)


def get_sections_with_items(guide):
    """Organize guide items by section for template rendering."""
    sections = {}

    # Use guide's sections if available (includes custom sections), otherwise use builtin
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


def get_valid_sections_for_guide(guide):
    """Get list of valid section keys for a guide (builtin + custom)."""
    if guide:
        return [s[0] for s in guide.get_all_sections()]
    return EPISODE_GUIDE_SECTION_CHOICES


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
        search_term = f"%{search}%"

        # Search in EpisodeGuide fields
        guide_conditions = or_(
            EpisodeGuide.title.ilike(search_term),
            EpisodeGuide.notes.ilike(search_term),
            EpisodeGuide.previous_poll.ilike(search_term),
            EpisodeGuide.new_poll.ilike(search_term),
        )

        # Subquery: check if any related EpisodeGuideItem matches
        item_exists = exists().where(
            EpisodeGuideItem.guide_id == EpisodeGuide.id,
            or_(
                EpisodeGuideItem.title.ilike(search_term),
                EpisodeGuideItem.link.ilike(search_term),  # Legacy single link
                EpisodeGuideItem.links.cast(db.String).ilike(search_term),  # Multiple links JSON
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
                    EpisodeGuideItem.link.ilike(search_term),  # Legacy single link
                    EpisodeGuideItem.links.cast(db.String).ilike(search_term),  # Multiple links JSON
                    EpisodeGuideItem.notes.ilike(search_term),
                )
            ).all()
            for item in items:
                matching_items.setdefault(item.guide_id, []).append(item)

    # Stats
    total = EpisodeGuide.query.count()
    drafts = EpisodeGuide.query.filter_by(status='draft').count()
    completed = EpisodeGuide.query.filter_by(status='completed').count()
    stats = {'total': total, 'drafts': drafts, 'completed': completed}

    # Check if this is an AJAX request for just the table
    if request.args.get('ajax') == '1':
        return render_template('episode_guide/_table.html',
            guides=pagination.items,
            search=search,
            matching_items=matching_items,
            stats=stats,
        )

    return render_template('episode_guide/list.html',
        guides=pagination.items,
        pagination=pagination,
        current_status=status,
        search=search,
        matching_items=matching_items,
        stats=stats,
    )


@episode_guide_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_guide():
    """Create a new episode guide."""
    # Get available templates for the form
    templates = EpisodeGuideTemplate.query.order_by(
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
                    EpisodeGuide.episode_number == episode_number - 1
                ).first()
                if prev_guide and prev_guide.new_poll:
                    previous_poll = prev_guide.new_poll
                    previous_poll_link = prev_guide.new_poll_link

            # Check if a template was selected
            template_id = form.integer('template_id')
            template = None
            if template_id:
                template = EpisodeGuideTemplate.query.get(template_id)

            guide = EpisodeGuide(
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
                # Apply default poll questions
                if template.default_poll_1:
                    guide.new_poll = template.default_poll_1
                if template.default_poll_2:
                    guide.new_poll_2 = template.default_poll_2

            db.session.add(guide)
            db.session.commit()
            flash(f'Episode guide "{guide.title}" created.', 'success')
            return redirect(url_for('episode_guide.edit_guide', id=guide.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('episode_guide/form.html', guide=None, templates=templates)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('episode_guide/form.html', guide=None, templates=templates)

    return render_template('episode_guide/form.html', guide=None, templates=templates)


@episode_guide_bp.route('/new-from/<int:source_id>', methods=['POST'])
@login_required
def copy_guide(source_id):
    """Create new guide by copying items from previous episode."""
    try:
        source = EpisodeGuide.query.options(joinedload(EpisodeGuide.items)).get_or_404(source_id)

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
                links=item.all_links.copy() if item.all_links else None,
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
    guide = EpisodeGuide.query.options(joinedload(EpisodeGuide.items)).get_or_404(id)
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
    guide = EpisodeGuide.query.options(joinedload(EpisodeGuide.items)).get_or_404(id)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            guide.title = form.required('title')
            guide.episode_number = form.integer('episode_number')
            guide.scheduled_date = form.date('scheduled_date')
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
        valid_sections = get_valid_sections_for_guide(guide)
        if section not in valid_sections:
            return jsonify({'success': False, 'error': 'Invalid section'}), 400

        title = data.get('title', '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        # Get max position in section
        max_pos = db.session.query(db.func.max(EpisodeGuideItem.position)).filter_by(
            guide_id=id, section=section
        ).scalar() or -1

        # Handle links (support both new 'links' array and legacy 'link' single value)
        links = data.get('links', [])
        single_link = (data.get('link') or '').strip()
        if single_link and not links:
            links = [single_link]
        # Filter empty strings and strip whitespace
        links = [l.strip() for l in links if l and l.strip()] or None

        item = EpisodeGuideItem(
            guide_id=id,
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

        if 'links' in data:
            # Handle links array
            links = data['links'] if isinstance(data['links'], list) else []
            item.links = [l.strip() for l in links if l and l.strip()] or None
        elif 'link' in data:
            # Legacy single link support
            single_link = (data['link'] or '').strip()
            item.links = [single_link] if single_link else None

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
        guide = EpisodeGuide.query.get_or_404(id)
        data = request.get_json()
        section = data.get('section')
        item_ids = data.get('item_ids', [])

        valid_sections = get_valid_sections_for_guide(guide)
        if section not in valid_sections:
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


@episode_guide_bp.route('/<int:id>/items/move', methods=['POST'])
@login_required
def move_item(id):
    """Move an item to a different section and/or position (AJAX)."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)
        data = request.get_json()
        item_id = data.get('item_id')
        target_section = data.get('target_section')
        new_position = data.get('new_position', 0)

        if not item_id:
            return jsonify({'success': False, 'error': 'item_id is required'}), 400
        valid_sections = get_valid_sections_for_guide(guide)
        if target_section not in valid_sections:
            return jsonify({'success': False, 'error': 'Invalid target section'}), 400
        if not isinstance(new_position, int) or new_position < 0:
            return jsonify({'success': False, 'error': 'Invalid position'}), 400

        item = EpisodeGuideItem.query.filter_by(id=item_id, guide_id=id).first_or_404()
        old_section = item.section
        old_position = item.position

        if old_section != target_section:
            # Cross-section move: update positions in both sections
            # Shift items down in old section (items after this one move up)
            EpisodeGuideItem.query.filter(
                EpisodeGuideItem.guide_id == id,
                EpisodeGuideItem.section == old_section,
                EpisodeGuideItem.position > old_position
            ).update({EpisodeGuideItem.position: EpisodeGuideItem.position - 1}, synchronize_session=False)

            # Shift items down in new section (items at/after target move down)
            EpisodeGuideItem.query.filter(
                EpisodeGuideItem.guide_id == id,
                EpisodeGuideItem.section == target_section,
                EpisodeGuideItem.position >= new_position
            ).update({EpisodeGuideItem.position: EpisodeGuideItem.position + 1}, synchronize_session=False)

            item.section = target_section
            item.position = new_position
        else:
            # Same section reorder
            if new_position > old_position:
                # Moving down: shift items between old and new position up
                EpisodeGuideItem.query.filter(
                    EpisodeGuideItem.guide_id == id,
                    EpisodeGuideItem.section == old_section,
                    EpisodeGuideItem.position > old_position,
                    EpisodeGuideItem.position <= new_position
                ).update({EpisodeGuideItem.position: EpisodeGuideItem.position - 1}, synchronize_session=False)
            elif new_position < old_position:
                # Moving up: shift items between new and old position down
                EpisodeGuideItem.query.filter(
                    EpisodeGuideItem.guide_id == id,
                    EpisodeGuideItem.section == old_section,
                    EpisodeGuideItem.position >= new_position,
                    EpisodeGuideItem.position < old_position
                ).update({EpisodeGuideItem.position: EpisodeGuideItem.position + 1}, synchronize_session=False)

            item.position = new_position

        # Refresh the item to get accurate position after bulk updates
        db.session.refresh(item)

        db.session.commit()

        return jsonify({
            'success': True,
            'item': item.to_dict(),
            'old_section': old_section,
            'new_section': target_section
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ---- Live Recording Mode ----

@episode_guide_bp.route('/<int:id>/live')
@login_required
def live_mode(id):
    """Live recording interface with timer and timestamp buttons."""
    guide = EpisodeGuide.query.options(joinedload(EpisodeGuide.items)).get_or_404(id)
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


# ---- Template Management ----

@episode_guide_bp.route('/templates')
@login_required
def list_templates():
    """List all episode guide templates."""
    templates = EpisodeGuideTemplate.query.order_by(
        EpisodeGuideTemplate.is_default.desc(),
        EpisodeGuideTemplate.name
    ).all()

    return render_template('episode_guide/templates_list.html',
        templates=templates,
    )


@episode_guide_bp.route('/templates/new', methods=['GET', 'POST'])
@login_required
def new_template():
    """Create a new episode guide template."""
    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Parse static content from textarea (one line per item)
            intro_lines = [line.strip() for line in form.optional('intro_static_content', '').split('\n') if line.strip()]
            outro_lines = [line.strip() for line in form.optional('outro_static_content', '').split('\n') if line.strip()]

            # Parse default sections from checkboxes
            selected_sections = request.form.getlist('default_sections')
            default_sections = []
            for key, name, parent in EPISODE_GUIDE_SECTIONS:
                if key in selected_sections:
                    default_sections.append({'key': key, 'name': name, 'parent': parent})

            template = EpisodeGuideTemplate(
                name=form.required('name'),
                description=form.optional('description'),
                intro_static_content=intro_lines if intro_lines else None,
                outro_static_content=outro_lines if outro_lines else None,
                default_sections=default_sections if default_sections else None,
                default_poll_1=form.optional('default_poll_1'),
                default_poll_2=form.optional('default_poll_2'),
                created_by=current_user.id,
                is_default=form.optional('is_default') == 'on',
            )

            # If this is set as default, clear other defaults
            if template.is_default:
                EpisodeGuideTemplate.query.filter(
                    EpisodeGuideTemplate.id != template.id
                ).update({'is_default': False})

            db.session.add(template)
            db.session.commit()
            flash(f'Template "{template.name}" created.', 'success')
            return redirect(url_for('episode_guide.list_templates'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('episode_guide/template_form.html',
        template=None,
        all_sections=EPISODE_GUIDE_SECTIONS,
        default_intro=INTRO_STATIC_CONTENT,
        default_outro=OUTRO_STATIC_CONTENT,
    )


@episode_guide_bp.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    """Edit an existing episode guide template."""
    template = EpisodeGuideTemplate.query.get_or_404(id)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Parse static content from textarea
            intro_lines = [line.strip() for line in form.optional('intro_static_content', '').split('\n') if line.strip()]
            outro_lines = [line.strip() for line in form.optional('outro_static_content', '').split('\n') if line.strip()]

            # Parse default sections from checkboxes
            selected_sections = request.form.getlist('default_sections')
            default_sections = []
            for key, name, parent in EPISODE_GUIDE_SECTIONS:
                if key in selected_sections:
                    default_sections.append({'key': key, 'name': name, 'parent': parent})

            template.name = form.required('name')
            template.description = form.optional('description')
            template.intro_static_content = intro_lines if intro_lines else None
            template.outro_static_content = outro_lines if outro_lines else None
            template.default_sections = default_sections if default_sections else None
            template.default_poll_1 = form.optional('default_poll_1')
            template.default_poll_2 = form.optional('default_poll_2')
            template.is_default = form.optional('is_default') == 'on'

            # If this is set as default, clear other defaults
            if template.is_default:
                EpisodeGuideTemplate.query.filter(
                    EpisodeGuideTemplate.id != template.id
                ).update({'is_default': False})

            db.session.commit()
            flash(f'Template "{template.name}" updated.', 'success')
            return redirect(url_for('episode_guide.list_templates'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('episode_guide/template_form.html',
        template=template,
        all_sections=EPISODE_GUIDE_SECTIONS,
        default_intro=INTRO_STATIC_CONTENT,
        default_outro=OUTRO_STATIC_CONTENT,
    )


@episode_guide_bp.route('/templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    """Delete an episode guide template."""
    try:
        template = EpisodeGuideTemplate.query.get_or_404(id)

        # Check if any guides are using this template
        guide_count = template.guides.count()
        if guide_count > 0:
            flash(f'Cannot delete template - it is used by {guide_count} guide(s).', 'error')
            return redirect(url_for('episode_guide.list_templates'))

        name = template.name
        db.session.delete(template)
        db.session.commit()
        flash(f'Template "{name}" deleted.', 'success')

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('episode_guide.list_templates'))


# ---- Custom Sections ----

@episode_guide_bp.route('/<int:id>/sections', methods=['POST'])
@login_required
def add_custom_section(id):
    """Add a custom section to an episode guide (AJAX)."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)
        data = request.get_json()

        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Section name is required'}), 400

        # Generate a key from the name
        key = name.lower().replace(' ', '_').replace('-', '_')
        # Remove any non-alphanumeric characters except underscore
        key = ''.join(c for c in key if c.isalnum() or c == '_')
        # Ensure key is unique by adding a suffix if needed
        base_key = key
        counter = 1
        existing_keys = get_valid_sections_for_guide(guide)
        while key in existing_keys:
            key = f"{base_key}_{counter}"
            counter += 1

        # Get optional parent and color
        parent = data.get('parent') or None
        color = data.get('color') or 'gray'

        # Add to custom_sections
        custom_sections = guide.custom_sections or []
        new_section = {
            'key': key,
            'name': name,
            'parent': parent,
            'color': color,
        }
        custom_sections.append(new_section)
        guide.custom_sections = custom_sections

        db.session.commit()

        return jsonify({
            'success': True,
            'section': new_section,
            'all_sections': [{'key': s[0], 'name': s[1], 'parent': s[2]} for s in guide.get_all_sections()],
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@episode_guide_bp.route('/<int:id>/sections/<section_key>', methods=['DELETE'])
@login_required
def delete_custom_section(id, section_key):
    """Delete a custom section from an episode guide (AJAX)."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)

        # Can only delete custom sections, not builtin ones
        if section_key in EPISODE_GUIDE_SECTION_CHOICES:
            return jsonify({'success': False, 'error': 'Cannot delete built-in sections'}), 400

        # Check if section has items
        item_count = EpisodeGuideItem.query.filter_by(guide_id=id, section=section_key).count()
        if item_count > 0:
            return jsonify({'success': False, 'error': f'Section has {item_count} items. Move or delete them first.'}), 400

        # Remove from custom_sections
        if guide.custom_sections:
            guide.custom_sections = [s for s in guide.custom_sections if s['key'] != section_key]
            if not guide.custom_sections:
                guide.custom_sections = None

        db.session.commit()

        return jsonify({'success': True})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ---- Static Content Management ----

@episode_guide_bp.route('/<int:id>/static-content', methods=['PUT'])
@login_required
def update_static_content(id):
    """Update intro/outro static content for a guide (AJAX)."""
    try:
        guide = EpisodeGuide.query.get_or_404(id)
        data = request.get_json()

        if 'intro_static_content' in data:
            content = data['intro_static_content']
            if isinstance(content, list):
                guide.intro_static_content = [line.strip() for line in content if line and line.strip()] or None
            elif isinstance(content, str):
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                guide.intro_static_content = lines if lines else None
            else:
                guide.intro_static_content = None

        if 'outro_static_content' in data:
            content = data['outro_static_content']
            if isinstance(content, list):
                guide.outro_static_content = [line.strip() for line in content if line and line.strip()] or None
            elif isinstance(content, str):
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                guide.outro_static_content = lines if lines else None
            else:
                guide.outro_static_content = None

        db.session.commit()

        return jsonify({
            'success': True,
            'intro_static_content': guide.get_intro_content(),
            'outro_static_content': guide.get_outro_content(),
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500