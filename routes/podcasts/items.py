"""Episode items, sections, and recording AJAX endpoints."""
from datetime import datetime, timezone
from flask import request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import EpisodeGuide, EpisodeGuideItem
from constants import EPISODE_GUIDE_SECTION_CHOICES
from utils.logging import log_exception
from utils.podcast_access import require_podcast_access

from . import podcast_bp


def get_valid_sections_for_guide(guide):
    """Get all valid section keys for a guide (builtins + custom)."""
    valid = set(EPISODE_GUIDE_SECTION_CHOICES)
    if guide.custom_sections:
        for cs in guide.custom_sections:
            if isinstance(cs, dict):
                valid.add(cs['key'])
            elif isinstance(cs, str):
                valid.add(cs)
    return valid


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
            for item in guide.items:
                item.timestamp_seconds = None
                item.discussed = False

        db.session.commit()
        return jsonify({'success': True, 'guide': guide.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Toggle recording', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/items/move', methods=['POST'])
@login_required
@require_podcast_access
def move_item(podcast_id, episode_id):
    """Move an item to a different section and/or position (AJAX)."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
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

        item = EpisodeGuideItem.query.filter_by(id=item_id, guide_id=episode_id).first_or_404()
        old_section = item.section
        old_position = item.position

        if old_section != target_section:
            # Cross-section move
            EpisodeGuideItem.query.filter(
                EpisodeGuideItem.guide_id == episode_id,
                EpisodeGuideItem.section == old_section,
                EpisodeGuideItem.position > old_position
            ).update({EpisodeGuideItem.position: EpisodeGuideItem.position - 1}, synchronize_session=False)

            EpisodeGuideItem.query.filter(
                EpisodeGuideItem.guide_id == episode_id,
                EpisodeGuideItem.section == target_section,
                EpisodeGuideItem.position >= new_position
            ).update({EpisodeGuideItem.position: EpisodeGuideItem.position + 1}, synchronize_session=False)

            item.section = target_section
            item.position = new_position
        else:
            # Same section reorder
            if new_position > old_position:
                EpisodeGuideItem.query.filter(
                    EpisodeGuideItem.guide_id == episode_id,
                    EpisodeGuideItem.section == old_section,
                    EpisodeGuideItem.position > old_position,
                    EpisodeGuideItem.position <= new_position
                ).update({EpisodeGuideItem.position: EpisodeGuideItem.position - 1}, synchronize_session=False)
            elif new_position < old_position:
                EpisodeGuideItem.query.filter(
                    EpisodeGuideItem.guide_id == episode_id,
                    EpisodeGuideItem.section == old_section,
                    EpisodeGuideItem.position >= new_position,
                    EpisodeGuideItem.position < old_position
                ).update({EpisodeGuideItem.position: EpisodeGuideItem.position + 1}, synchronize_session=False)

            item.position = new_position

        db.session.commit()
        db.session.refresh(item)

        return jsonify({
            'success': True,
            'item': item.to_dict(),
            'old_section': old_section,
            'new_section': target_section
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Move item', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/sections', methods=['POST'])
@login_required
@require_podcast_access
def add_custom_section(podcast_id, episode_id):
    """Add a custom section to an episode guide (AJAX)."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        data = request.get_json()
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Section name is required'}), 400

        key = name.lower().replace(' ', '_').replace('-', '_')
        key = ''.join(c for c in key if c.isalnum() or c == '_')
        base_key = key
        counter = 1
        existing_keys = get_valid_sections_for_guide(guide)
        while key in existing_keys:
            key = f"{base_key}_{counter}"
            counter += 1

        parent = data.get('parent') or None
        color = data.get('color') or 'gray'

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
        log_exception(current_app.logger, 'Add custom section', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/sections/<section_key>', methods=['DELETE'])
@login_required
@require_podcast_access
def delete_custom_section(podcast_id, episode_id, section_key):
    """Delete a custom section from an episode guide (AJAX)."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        if section_key in EPISODE_GUIDE_SECTION_CHOICES:
            return jsonify({'success': False, 'error': 'Cannot delete built-in sections'}), 400

        item_count = EpisodeGuideItem.query.filter_by(guide_id=episode_id, section=section_key).count()
        if item_count > 0:
            return jsonify({'success': False, 'error': f'Section has {item_count} items. Move or delete them first.'}), 400

        if guide.custom_sections:
            guide.custom_sections = [s for s in guide.custom_sections if s['key'] != section_key]
            if not guide.custom_sections:
                guide.custom_sections = None

        db.session.commit()
        return jsonify({'success': True})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete custom section', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/start', methods=['POST'])
@login_required
@require_podcast_access
def start_recording(podcast_id, episode_id):
    """Start the timer / begin recording (AJAX)."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
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
        log_exception(current_app.logger, 'Start recording', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/stop', methods=['POST'])
@login_required
@require_podcast_access
def stop_recording(podcast_id, episode_id):
    """Stop the timer / end recording (AJAX)."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
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
        log_exception(current_app.logger, 'Stop recording', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/timestamp/<int:item_id>', methods=['POST'])
@login_required
@require_podcast_access
def capture_timestamp(podcast_id, episode_id, item_id):
    """Capture current timestamp for an item (AJAX)."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        item = EpisodeGuideItem.query.filter_by(id=item_id, guide_id=episode_id).first_or_404()
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
        log_exception(current_app.logger, 'Capture timestamp', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/static-content', methods=['PUT'])
@login_required
@require_podcast_access
def update_static_content(podcast_id, episode_id):
    """Update intro/outro static content for a guide (AJAX)."""
    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
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
        log_exception(current_app.logger, 'Update static content', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500
