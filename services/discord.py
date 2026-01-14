"""Discord integration service for community topic sourcing.

This service handles:
- Fetching messages from Discord channels
- Filtering messages by emoji reactions
- Supporting both Unicode and custom Discord emoji
"""

import re
import requests
from datetime import datetime, timezone
from flask import current_app

# Discord epoch: January 1, 2015 00:00:00 UTC (in milliseconds)
DISCORD_EPOCH = 1420070400000


def date_to_snowflake(dt):
    """
    Convert a datetime or date to a Discord snowflake ID.

    Discord snowflakes encode timestamps. This allows using the `after`
    parameter to fetch messages after a specific date.

    Args:
        dt: datetime or date object

    Returns:
        str: Discord snowflake ID representing the start of that day
    """
    if hasattr(dt, 'timestamp'):
        # datetime object
        ts_ms = int(dt.timestamp() * 1000)
    else:
        # date object - convert to datetime at start of day UTC
        dt_obj = datetime.combine(dt, datetime.min.time(), tzinfo=timezone.utc)
        ts_ms = int(dt_obj.timestamp() * 1000)

    # Discord snowflake format: (timestamp_ms - DISCORD_EPOCH) << 22
    snowflake = (ts_ms - DISCORD_EPOCH) << 22
    return str(snowflake)


class DiscordService:
    """Service for Discord API interactions."""

    BASE_URL = 'https://discord.com/api/v10'

    def __init__(self, bot_token=None, channel_id=None):
        """
        Initialize Discord service.

        Args:
            bot_token: Discord bot token (or fetched from config)
            channel_id: Discord channel ID to monitor
        """
        self.bot_token = bot_token
        self.channel_id = channel_id

    @property
    def is_configured(self):
        """Check if Discord API is configured."""
        return bool(self.bot_token and self.channel_id)

    def _headers(self):
        """Get authorization headers for Discord API."""
        return {
            'Authorization': f'Bot {self.bot_token}',
            'Content-Type': 'application/json',
        }

    def _make_request(self, method, endpoint, **kwargs):
        """Make a request to Discord API with error handling."""
        url = f"{self.BASE_URL}{endpoint}"
        kwargs.setdefault('timeout', 10)
        kwargs['headers'] = self._headers()

        try:
            resp = requests.request(method, url, **kwargs)
            resp.raise_for_status()
            return {'success': True, 'data': resp.json()}
        except requests.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('message', str(e))
                except ValueError:
                    error_msg = e.response.text or str(e)
            return {'success': False, 'error': error_msg}

    def get_channel_info(self):
        """Get information about the configured channel."""
        if not self.is_configured:
            return {'success': False, 'error': 'Discord not configured'}

        result = self._make_request('GET', f'/channels/{self.channel_id}')
        if result['success']:
            channel = result['data']
            return {
                'success': True,
                'channel': {
                    'id': channel.get('id'),
                    'name': channel.get('name'),
                    'guild_id': channel.get('guild_id'),
                    'type': channel.get('type'),
                }
            }
        return result

    def get_messages(self, limit=100, before=None, after=None):
        """
        Fetch messages from the configured channel.

        Args:
            limit: Number of messages to fetch (max 100 per request)
            before: Get messages before this message ID
            after: Get messages after this message ID

        Returns:
            dict with 'success', 'messages' list or 'error'
        """
        if not self.is_configured:
            return {'success': False, 'error': 'Discord not configured', 'messages': []}

        params = {'limit': min(limit, 100)}
        if before:
            params['before'] = before
        if after:
            params['after'] = after

        result = self._make_request('GET', f'/channels/{self.channel_id}/messages', params=params)
        if result['success']:
            return {'success': True, 'messages': result['data']}
        return {'success': False, 'error': result.get('error'), 'messages': []}

    def get_messages_with_reactions(self, emoji_mapping, limit=100, after=None, exclude_message_ids=None):
        """
        Fetch messages that have specific emoji reactions.

        Args:
            emoji_mapping: Dict mapping emoji to section_key, e.g.:
                           {"🐭": "news_mice", "<:custom:123>": "news_other"}
            limit: Maximum number of messages to check
            after: Only get messages after this message ID
            exclude_message_ids: Set of message IDs to skip (already imported)

        Returns:
            dict with 'success', 'messages' list (each with 'suggested_section')
        """
        if not self.is_configured:
            return {'success': False, 'error': 'Discord not configured', 'messages': []}

        exclude_ids = set(exclude_message_ids or [])

        result = self.get_messages(limit=limit, after=after)
        if not result['success']:
            return result

        filtered_messages = []
        for msg in result.get('messages', []):
            # Skip already imported messages
            if msg.get('id') in exclude_ids:
                continue

            reactions = msg.get('reactions', [])
            matched_emoji = None
            matched_section = None

            for reaction in reactions:
                reaction_emoji = reaction.get('emoji', {})

                # Build emoji identifier
                # Custom emoji: <:name:id> or <a:name:id> (animated)
                # Unicode emoji: just the name field
                emoji_id = reaction_emoji.get('id')
                emoji_name = reaction_emoji.get('name', '')

                if emoji_id:
                    # Custom emoji - build Discord format
                    animated = reaction_emoji.get('animated', False)
                    prefix = '<a:' if animated else '<:'
                    emoji_identifier = f"{prefix}{emoji_name}:{emoji_id}>"
                else:
                    # Unicode emoji
                    emoji_identifier = emoji_name

                # Check if this emoji is in our mapping
                if emoji_identifier in emoji_mapping:
                    matched_emoji = emoji_identifier
                    matched_section = emoji_mapping[emoji_identifier]
                    break
                # Also check just the name for custom emoji flexibility
                elif emoji_name in emoji_mapping:
                    matched_emoji = emoji_name
                    matched_section = emoji_mapping[emoji_name]
                    break

            if matched_section:
                parsed = self._parse_message(msg)
                parsed['suggested_section'] = matched_section
                parsed['matched_emoji'] = matched_emoji
                filtered_messages.append(parsed)

        return {'success': True, 'messages': filtered_messages}

    def get_messages_multi_channel(self, channel_ids, target_emoji, target_section,
                                   limit_per_channel=50, exclude_message_ids=None, after=None):
        """
        Scan multiple channels for messages with a specific emoji reaction.

        Args:
            channel_ids: List of channel IDs to scan
            target_emoji: Single emoji to look for (Unicode or custom Discord format)
            target_section: Section key to assign to all matched messages
            limit_per_channel: Max messages to fetch per channel (default 50)
            exclude_message_ids: Set of message IDs to skip (already imported)
            after: Only get messages after this message ID (snowflake)

        Returns:
            dict with 'success', 'messages' list, 'channels_scanned', 'errors'
        """
        if not self.bot_token:
            return {'success': False, 'error': 'Discord bot token not configured', 'messages': []}

        if not channel_ids:
            return {'success': False, 'error': 'No channel IDs provided', 'messages': []}

        if not target_emoji:
            return {'success': False, 'error': 'No target emoji specified', 'messages': []}

        exclude_ids = set(exclude_message_ids or [])
        all_messages = []
        channels_scanned = []
        errors = []

        # Store original channel_id to restore later
        original_channel_id = self.channel_id

        for channel_id in channel_ids:
            # Temporarily set channel_id for API call
            self.channel_id = channel_id

            result = self.get_messages(limit=limit_per_channel, after=after)
            if not result['success']:
                errors.append({'channel_id': channel_id, 'error': result.get('error')})
                continue

            channels_scanned.append(channel_id)

            for msg in result.get('messages', []):
                # Skip already imported messages
                if msg.get('id') in exclude_ids:
                    continue

                reactions = msg.get('reactions', [])
                matched = False

                for reaction in reactions:
                    reaction_emoji = reaction.get('emoji', {})
                    emoji_id = reaction_emoji.get('id')
                    emoji_name = reaction_emoji.get('name', '')

                    if emoji_id:
                        animated = reaction_emoji.get('animated', False)
                        prefix = '<a:' if animated else '<:'
                        emoji_identifier = f"{prefix}{emoji_name}:{emoji_id}>"
                    else:
                        emoji_identifier = emoji_name

                    # Check if this matches our target emoji
                    if emoji_identifier == target_emoji or emoji_name == target_emoji:
                        matched = True
                        break

                if matched:
                    parsed = self._parse_message(msg)
                    parsed['suggested_section'] = target_section
                    parsed['matched_emoji'] = target_emoji
                    parsed['source_channel_id'] = channel_id
                    all_messages.append(parsed)

        # Restore original channel_id
        self.channel_id = original_channel_id

        return {
            'success': True,
            'messages': all_messages,
            'channels_scanned': len(channels_scanned),
            'total_channels': len(channel_ids),
            'errors': errors
        }

    def _parse_message(self, msg):
        """
        Parse a Discord message into a simplified format.

        Args:
            msg: Raw Discord message object

        Returns:
            Simplified message dict
        """
        content = msg.get('content', '')

        # Extract URLs from content
        url_pattern = r'https?://[^\s<>\"\']+|www\.[^\s<>\"\']+\.[^\s<>\"\']+'
        urls = re.findall(url_pattern, content)
        link = urls[0] if urls else None

        # Also check embeds for URLs
        embeds = msg.get('embeds', [])
        if not link and embeds:
            for embed in embeds:
                if embed.get('url'):
                    link = embed['url']
                    break

        # Get author info
        author = msg.get('author', {})

        # Get all reactions for display
        reactions = []
        for reaction in msg.get('reactions', []):
            emoji = reaction.get('emoji', {})
            emoji_id = emoji.get('id')
            emoji_name = emoji.get('name', '')

            if emoji_id:
                animated = emoji.get('animated', False)
                prefix = '<a:' if animated else '<:'
                display = f"{prefix}{emoji_name}:{emoji_id}>"
            else:
                display = emoji_name

            reactions.append({
                'emoji': display,
                'count': reaction.get('count', 0),
            })

        return {
            'id': msg.get('id'),
            'content': content,
            'link': link,
            'all_links': urls,
            'author': {
                'id': author.get('id'),
                'username': author.get('username'),
                'display_name': author.get('global_name') or author.get('username'),
            },
            'timestamp': msg.get('timestamp'),
            'reactions': reactions,
            'embeds': [{
                'title': e.get('title'),
                'description': e.get('description'),
                'url': e.get('url'),
            } for e in embeds],
        }

    @classmethod
    def from_integration(cls, integration):
        """
        Create a DiscordService from a DiscordIntegration model instance.

        Args:
            integration: DiscordIntegration model instance

        Returns:
            DiscordService instance
        """
        return cls(
            bot_token=integration.get_bot_token(),
            channel_id=integration.channel_id
        )

    @classmethod
    def get_emoji_mapping_from_integration(cls, integration):
        """
        Build emoji mapping dict from integration's emoji_mappings.

        Args:
            integration: DiscordIntegration model instance

        Returns:
            Dict mapping emoji string to section_key
        """
        return {m.emoji: m.section_key for m in integration.emoji_mappings}
