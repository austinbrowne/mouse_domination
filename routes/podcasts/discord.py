"""Discord integration routes for podcasts."""
from datetime import timedelta
from flask import request, jsonify, g, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import (
    EpisodeGuide, EpisodeGuideItem, EpisodeGuideTemplate,
    DiscordIntegration, DiscordEmojiMapping, DiscordImportLog
)
from constants import EPISODE_GUIDE_SECTION_CHOICES, EPISODE_GUIDE_SECTION_NAMES
from utils.logging import log_exception
from utils.podcast_access import require_podcast_admin

from .items import get_valid_sections_for_guide
from . import podcast_bp


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/discord', methods=['GET', 'POST'])
@login_required
@require_podcast_admin
def manage_discord_integration(podcast_id, template_id):
    """Manage Discord integration for a template (create or update)."""
    template = EpisodeGuideTemplate.query.filter_by(
        id=template_id,
        podcast_id=podcast_id
    ).first_or_404()

    if request.method == 'POST':
        try:
            data = request.get_json()

            integration = template.discord_integration
            if not integration:
                integration = DiscordIntegration(template_id=template_id)
                db.session.add(integration)

            integration.name = (data.get('name') or f"{template.name} Discord").strip()
            integration.guild_id = (data.get('guild_id') or '').strip()
            integration.bot_token_env_var = (data.get('bot_token_env_var') or 'DISCORD_BOT_TOKEN').strip()
            integration.is_active = data.get('is_active', True)

            # Unified channel_ids field (can be single or comma-separated)
            channel_ids = (data.get('channel_ids') or '').strip()
            integration.scan_channel_ids = channel_ids
            # Also set channel_id to first channel for backward compatibility
            first_channel = channel_ids.split(',')[0].strip() if channel_ids else ''
            integration.channel_id = first_channel

            integration.scan_emoji = (data.get('scan_emoji') or '').strip()

            if not integration.guild_id:
                return jsonify({'success': False, 'error': 'Guild ID is required'}), 400

            if not channel_ids:
                return jsonify({'success': False, 'error': 'At least one Channel ID is required'}), 400

            if not integration.scan_emoji:
                return jsonify({'success': False, 'error': 'Emoji to scan for is required'}), 400

            db.session.commit()

            return jsonify({
                'success': True,
                'integration': integration.to_dict()
            })

        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Manage Discord integration', e)
            return jsonify({'success': False, 'error': 'Database error'}), 500

    integration = template.discord_integration
    return jsonify({
        'success': True,
        'integration': integration.to_dict() if integration else None,
        'template': {'id': template.id, 'name': template.name}
    })


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/discord/delete', methods=['POST'])
@login_required
@require_podcast_admin
def delete_discord_integration(podcast_id, template_id):
    """Delete Discord integration for a template."""
    try:
        template = EpisodeGuideTemplate.query.filter_by(
            id=template_id,
            podcast_id=podcast_id
        ).first_or_404()
        integration = template.discord_integration

        if not integration:
            return jsonify({'success': False, 'error': 'No integration found'}), 404

        db.session.delete(integration)
        db.session.commit()

        return jsonify({'success': True})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete Discord integration', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/discord/test', methods=['POST'])
@login_required
@require_podcast_admin
def test_discord_connection(podcast_id, template_id):
    """Test Discord connection for a template's integration."""
    from services.discord import DiscordService

    template = EpisodeGuideTemplate.query.filter_by(
        id=template_id,
        podcast_id=podcast_id
    ).first_or_404()
    integration = template.discord_integration

    if not integration:
        return jsonify({'success': False, 'error': 'No Discord integration configured'}), 400

    service = DiscordService.from_integration(integration)

    if not service.is_configured:
        return jsonify({
            'success': False,
            'error': f'Discord not configured. Check {integration.bot_token_env_var} environment variable.'
        }), 400

    result = service.get_channel_info()
    if result.get('success'):
        return jsonify({
            'success': True,
            'channel': result['channel'],
            'message': f"Connected to #{result['channel'].get('name', 'unknown')}"
        })
    else:
        return jsonify({
            'success': False,
            'error': result.get('error', 'Connection failed')
        }), 502  # Bad Gateway - external service failed


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/discord/emoji-mappings', methods=['GET', 'POST'])
@login_required
@require_podcast_admin
def manage_emoji_mappings(podcast_id, template_id):
    """Manage emoji-to-section mappings for a template's Discord integration."""
    template = EpisodeGuideTemplate.query.filter_by(
        id=template_id,
        podcast_id=podcast_id
    ).first_or_404()
    integration = template.discord_integration

    if not integration:
        return jsonify({'success': False, 'error': 'No Discord integration configured'}), 400

    if request.method == 'POST':
        try:
            data = request.get_json()

            emoji = (data.get('emoji') or '').strip()
            section_key = (data.get('section_key') or '').strip()

            if not emoji or not section_key:
                return jsonify({'success': False, 'error': 'Emoji and section are required'}), 400

            valid_sections = list(EPISODE_GUIDE_SECTION_CHOICES)
            if template.default_sections:
                valid_sections.extend([s['key'] for s in template.default_sections])
            if section_key not in valid_sections:
                return jsonify({'success': False, 'error': 'Invalid section'}), 400

            existing = DiscordEmojiMapping.query.filter_by(
                integration_id=integration.id, emoji=emoji
            ).first()
            if existing:
                return jsonify({'success': False, 'error': 'This emoji is already mapped'}), 400

            max_order = db.session.query(db.func.max(DiscordEmojiMapping.display_order)).filter_by(
                integration_id=integration.id
            ).scalar() or -1

            mapping = DiscordEmojiMapping(
                integration_id=integration.id,
                emoji=emoji,
                emoji_name=data.get('emoji_name', '').strip() or None,
                section_key=section_key,
                display_order=max_order + 1
            )
            db.session.add(mapping)
            db.session.commit()

            return jsonify({
                'success': True,
                'mapping': mapping.to_dict()
            })

        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Manage emoji mappings', e)
            return jsonify({'success': False, 'error': 'Database error'}), 500

    return jsonify({
        'success': True,
        'mappings': [m.to_dict() for m in integration.emoji_mappings],
        'sections': EPISODE_GUIDE_SECTION_NAMES
    })


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/discord/emoji-mappings/<int:mapping_id>', methods=['PUT', 'DELETE'])
@login_required
@require_podcast_admin
def update_or_delete_emoji_mapping(podcast_id, template_id, mapping_id):
    """Update or delete an emoji mapping."""
    try:
        template = EpisodeGuideTemplate.query.filter_by(
            id=template_id,
            podcast_id=podcast_id
        ).first_or_404()
        integration = template.discord_integration

        if not integration:
            return jsonify({'success': False, 'error': 'No Discord integration configured'}), 400

        mapping = DiscordEmojiMapping.query.filter_by(
            id=mapping_id, integration_id=integration.id
        ).first_or_404()

        if request.method == 'DELETE':
            db.session.delete(mapping)
            db.session.commit()
            return jsonify({'success': True})

        # PUT - Update
        data = request.get_json()

        if 'emoji' in data:
            new_emoji = (data['emoji'] or '').strip()
            if new_emoji and new_emoji != mapping.emoji:
                existing = DiscordEmojiMapping.query.filter(
                    DiscordEmojiMapping.integration_id == integration.id,
                    DiscordEmojiMapping.emoji == new_emoji,
                    DiscordEmojiMapping.id != mapping_id
                ).first()
                if existing:
                    return jsonify({'success': False, 'error': 'This emoji is already mapped'}), 400
                mapping.emoji = new_emoji

        if 'emoji_name' in data:
            mapping.emoji_name = (data['emoji_name'] or '').strip() or None

        if 'section_key' in data:
            section_key = (data['section_key'] or '').strip()
            if section_key:
                valid_sections = list(EPISODE_GUIDE_SECTION_CHOICES)
                if template.default_sections:
                    valid_sections.extend([s['key'] for s in template.default_sections])
                if section_key not in valid_sections:
                    return jsonify({'success': False, 'error': 'Invalid section'}), 400
                mapping.section_key = section_key

        db.session.commit()
        return jsonify({'success': True, 'mapping': mapping.to_dict()})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Update emoji mapping', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/discord/fetch', methods=['POST'])
@login_required
@require_podcast_admin
def discord_fetch_messages(podcast_id, episode_id):
    """Fetch messages from Discord for potential import."""
    from services.discord import DiscordService, date_to_snowflake

    guide = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    if not guide.template:
        return jsonify({'success': False, 'error': 'Guide has no template assigned'}), 400

    integration = guide.template.discord_integration
    if not integration or not integration.is_active:
        return jsonify({'success': False, 'error': 'No active Discord integration for this template'}), 400

    from datetime import datetime

    data = request.get_json() or {}
    limit = min(data.get('limit', 50), 100)

    after_snowflake = None
    last_episode_date = None

    # Check for custom date override from frontend
    custom_after_date = data.get('after_date')
    if custom_after_date:
        try:
            custom_date = datetime.strptime(custom_after_date, '%Y-%m-%d').date()
            after_snowflake = date_to_snowflake(custom_date)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
    else:
        # Auto-detect from last completed episode
        last_episode = EpisodeGuide.query.filter(
            EpisodeGuide.template_id == guide.template_id,
            EpisodeGuide.id != episode_id,
            EpisodeGuide.status == 'completed',
            EpisodeGuide.scheduled_date.isnot(None)
        ).order_by(EpisodeGuide.scheduled_date.desc()).first()

        if last_episode and last_episode.scheduled_date:
            cutoff_date = last_episode.scheduled_date + timedelta(days=1)
            after_snowflake = date_to_snowflake(cutoff_date)
            last_episode_date = last_episode.scheduled_date.isoformat()

    imported_ids = {
        log.discord_message_id for log in
        DiscordImportLog.query.filter_by(guide_id=episode_id).all()
    }

    # Get channel list (unified approach)
    channel_ids = integration.get_scan_channel_list()
    if not channel_ids and integration.channel_id:
        channel_ids = [integration.channel_id]

    if not channel_ids:
        return jsonify({'success': False, 'error': 'No channel IDs configured'}), 400

    if not integration.scan_emoji:
        return jsonify({'success': False, 'error': 'No emoji configured. Set it in template settings.'}), 400

    service = DiscordService(
        bot_token=integration.get_bot_token(),
        channel_id=None
    )

    if not service.bot_token:
        return jsonify({
            'success': False,
            'error': f'Discord not configured. Check {integration.bot_token_env_var} environment variable.'
        }), 400

    # Fetch messages with the configured emoji (no section pre-assignment)
    result = service.get_messages_multi_channel(
        channel_ids=channel_ids,
        target_emoji=integration.scan_emoji,
        target_section=None,  # No auto-assignment, user picks at import time
        limit_per_channel=limit,
        exclude_message_ids=imported_ids,
        after=after_snowflake
    )

    if not result.get('success'):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to fetch messages')
        }), 400

    messages = result.get('messages', [])

    # Get valid sections for this guide (for the section picker in the modal)
    guide_sections = {}
    if guide.template and guide.template.default_sections:
        for section in guide.template.default_sections:
            if isinstance(section, dict):
                guide_sections[section['key']] = section.get('name', section['key'])
    # Also include standard sections
    guide_sections.update(EPISODE_GUIDE_SECTION_NAMES)

    return jsonify({
        'success': True,
        'messages': messages,
        'sections': guide_sections,
        'channel_name': integration.name,
        'channels_scanned': result.get('channels_scanned', 0),
        'total_channels': result.get('total_channels', 0),
        'errors': result.get('errors', []),
        'last_episode_date': last_episode_date
    })


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/discord/import', methods=['POST'])
@login_required
@require_podcast_admin
def discord_import_messages(podcast_id, episode_id):
    """Import selected Discord messages as episode guide items."""
    try:
        guide = EpisodeGuide.query.filter_by(
            id=episode_id,
            podcast_id=podcast_id
        ).first_or_404()

        if not guide.template:
            return jsonify({'success': False, 'error': 'Guide has no template assigned'}), 400

        integration = guide.template.discord_integration
        if not integration:
            return jsonify({'success': False, 'error': 'No Discord integration configured'}), 400

        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'success': False, 'error': 'No items provided'}), 400

        valid_sections = get_valid_sections_for_guide(guide)
        items_to_import = data['items']
        imported = []

        for item_data in items_to_import:
            section = item_data.get('section')
            if section not in valid_sections:
                continue

            title = (item_data.get('title') or '').strip()
            if not title:
                continue

            discord_message_id = item_data.get('discord_message_id')
            if not discord_message_id:
                continue

            existing = DiscordImportLog.query.filter_by(
                guide_id=episode_id, discord_message_id=discord_message_id
            ).first()
            if existing:
                continue

            max_pos = db.session.query(db.func.max(EpisodeGuideItem.position)).filter_by(
                guide_id=episode_id, section=section
            ).scalar() or -1

            links = item_data.get('links', [])
            if isinstance(links, str):
                links = [links] if links.strip() else []
            links = [l.strip() for l in links if l and l.strip()] or None

            item = EpisodeGuideItem(
                guide_id=episode_id,
                section=section,
                title=title[:500],
                links=links,
                notes=item_data.get('notes', '').strip()[:1000] or None,
                position=max_pos + 1,
            )
            db.session.add(item)
            db.session.flush()

            import_log = DiscordImportLog(
                integration_id=integration.id,
                guide_id=episode_id,
                discord_message_id=discord_message_id,
                item_id=item.id,
                imported_by=current_user.id
            )
            db.session.add(import_log)

            item_dict = item.to_dict()
            item_dict['discord_message_id'] = discord_message_id
            imported.append(item_dict)

        db.session.commit()

        return jsonify({
            'success': True,
            'imported': imported,
            'count': len(imported)
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Discord import', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/discord/skip', methods=['POST'])
@login_required
@require_podcast_admin
def discord_skip_message(podcast_id, episode_id):
    """Mark a Discord message as skipped (don't import, don't show again)."""
    try:
        guide = EpisodeGuide.query.filter_by(
            id=episode_id,
            podcast_id=podcast_id
        ).first_or_404()

        if not guide.template:
            return jsonify({'success': False, 'error': 'Guide has no template assigned'}), 400

        integration = guide.template.discord_integration
        if not integration:
            return jsonify({'success': False, 'error': 'No Discord integration configured'}), 400

        data = request.get_json()
        discord_message_id = data.get('discord_message_id')
        if not discord_message_id:
            return jsonify({'success': False, 'error': 'No message ID provided'}), 400

        # Check if already logged (imported or skipped)
        existing = DiscordImportLog.query.filter_by(
            guide_id=episode_id, discord_message_id=discord_message_id
        ).first()
        if existing:
            return jsonify({'success': True, 'already_skipped': True})

        # Create import log with item_id=None to mark as skipped
        skip_log = DiscordImportLog(
            integration_id=integration.id,
            guide_id=episode_id,
            discord_message_id=discord_message_id,
            item_id=None,  # No item created - this was skipped
            imported_by=current_user.id
        )
        db.session.add(skip_log)
        db.session.commit()

        return jsonify({'success': True})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Discord skip', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500
