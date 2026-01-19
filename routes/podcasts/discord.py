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
            integration.channel_id = (data.get('channel_id') or '').strip()
            integration.bot_token_env_var = (data.get('bot_token_env_var') or 'DISCORD_BOT_TOKEN').strip()
            integration.is_active = data.get('is_active', True)

            integration.scan_mode = data.get('scan_mode', 'single')
            integration.scan_channel_ids = (data.get('scan_channel_ids') or '').strip()
            integration.scan_emoji = (data.get('scan_emoji') or '').strip()
            integration.scan_target_section = (data.get('scan_target_section') or '').strip()

            if not integration.guild_id:
                return jsonify({'success': False, 'error': 'Guild ID is required'}), 400

            if integration.scan_mode == 'single' and not integration.channel_id:
                return jsonify({'success': False, 'error': 'Channel ID is required for single channel mode'}), 400
            elif integration.scan_mode == 'multi':
                if not integration.scan_channel_ids:
                    return jsonify({'success': False, 'error': 'Channel IDs are required for multi-channel mode'}), 400
                if not integration.scan_emoji:
                    return jsonify({'success': False, 'error': 'Scan emoji is required for multi-channel mode'}), 400

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
        return jsonify({'success': False, 'error': 'No Discord integration configured'})

    service = DiscordService.from_integration(integration)

    if not service.is_configured:
        return jsonify({
            'success': False,
            'error': f'Discord not configured. Check {integration.bot_token_env_var} environment variable.'
        })

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
        })


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

    after_snowflake = None
    last_episode_date = None
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

    data = request.get_json() or {}
    limit = min(data.get('limit', 50), 100)

    scan_mode = integration.scan_mode or 'single'

    if scan_mode == 'multi':
        channel_ids = integration.get_scan_channel_list()
        if not channel_ids:
            return jsonify({'success': False, 'error': 'No channel IDs configured for multi-channel mode'}), 400

        if not integration.scan_emoji:
            return jsonify({'success': False, 'error': 'No scan emoji configured for multi-channel mode'}), 400

        service = DiscordService(
            bot_token=integration.get_bot_token(),
            channel_id=None
        )

        if not service.bot_token:
            return jsonify({
                'success': False,
                'error': f'Discord not configured. Check {integration.bot_token_env_var} environment variable.'
            }), 400

        target_section = integration.scan_target_section or 'community_recap'

        result = service.get_messages_multi_channel(
            channel_ids=channel_ids,
            target_emoji=integration.scan_emoji,
            target_section=target_section,
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
        for msg in messages:
            section = msg.get('suggested_section')
            msg['section_display'] = EPISODE_GUIDE_SECTION_NAMES.get(section, section)

        return jsonify({
            'success': True,
            'messages': messages,
            'sections': EPISODE_GUIDE_SECTION_NAMES,
            'channel_name': f"{integration.name} (Multi-channel)",
            'scan_mode': 'multi',
            'channels_scanned': result.get('channels_scanned', 0),
            'total_channels': result.get('total_channels', 0),
            'errors': result.get('errors', []),
            'last_episode_date': last_episode_date
        })

    else:
        # Single channel mode
        if not integration.emoji_mappings:
            return jsonify({'success': False, 'error': 'No emoji mappings configured. Add them in the template settings.'}), 400

        service = DiscordService.from_integration(integration)
        if not service.is_configured:
            return jsonify({
                'success': False,
                'error': f'Discord not configured. Check {integration.bot_token_env_var} environment variable.'
            }), 400

        emoji_mapping = DiscordService.get_emoji_mapping_from_integration(integration)

        result = service.get_messages_with_reactions(
            emoji_mapping=emoji_mapping,
            limit=limit,
            exclude_message_ids=imported_ids,
            after=after_snowflake
        )

        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to fetch messages')
            }), 400

        messages = result.get('messages', [])
        for msg in messages:
            section = msg.get('suggested_section')
            msg['section_display'] = EPISODE_GUIDE_SECTION_NAMES.get(section, section)

        return jsonify({
            'success': True,
            'messages': messages,
            'sections': EPISODE_GUIDE_SECTION_NAMES,
            'channel_name': integration.name,
            'scan_mode': 'single',
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

            imported.append(item.to_dict())

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
