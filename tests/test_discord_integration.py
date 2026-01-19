"""Tests for Discord integration with simplified single-emoji approach."""
import pytest
from unittest.mock import patch, MagicMock
from models import (
    User, Podcast, PodcastMember, EpisodeGuide, EpisodeGuideTemplate,
    DiscordIntegration, DiscordImportLog, EpisodeGuideItem
)
from extensions import db


def create_podcast_with_user(user_dict, slug):
    """Helper to create a podcast with proper created_by field.

    Args:
        user_dict: Dict with 'id' key (from test fixtures)
        slug: Unique slug for the podcast
    """
    user_id = user_dict['id']
    podcast = Podcast(
        name='Test Podcast',
        slug=slug,
        created_by=user_id
    )
    db.session.add(podcast)
    db.session.flush()

    member = PodcastMember(
        podcast_id=podcast.id,
        user_id=user_id,
        role='admin'
    )
    db.session.add(member)
    return podcast


class TestDiscordIntegrationModel:
    """Test DiscordIntegration model."""

    def test_to_dict_includes_channel_ids(self, app, test_user):
        """Test that to_dict returns unified channel_ids field."""
        with app.app_context():
            podcast = create_podcast_with_user(test_user, 'test-podcast')

            template = EpisodeGuideTemplate(
                podcast_id=podcast.id,
                name='Test Template'
            )
            db.session.add(template)
            db.session.flush()

            integration = DiscordIntegration(
                template_id=template.id,
                name='Test Discord',
                guild_id='123456789',
                channel_id='111111111',
                scan_channel_ids='111111111,222222222,333333333',
                scan_emoji='🐭',
                bot_token_env_var='DISCORD_BOT_TOKEN'
            )
            db.session.add(integration)
            db.session.commit()

            data = integration.to_dict()

            assert data['channel_ids'] == '111111111,222222222,333333333'
            assert data['scan_emoji'] == '🐭'
            assert data['guild_id'] == '123456789'

    def test_get_scan_channel_list(self, app, test_user):
        """Test parsing comma-separated channel IDs."""
        with app.app_context():
            podcast = create_podcast_with_user(test_user, 'test-podcast-2')

            template = EpisodeGuideTemplate(
                podcast_id=podcast.id,
                name='Test Template'
            )
            db.session.add(template)
            db.session.flush()

            integration = DiscordIntegration(
                template_id=template.id,
                name='Test Discord',
                guild_id='123456789',
                channel_id='111',
                scan_channel_ids='111, 222, 333',
                scan_emoji='🐭'
            )
            db.session.add(integration)
            db.session.commit()

            channels = integration.get_scan_channel_list()
            assert channels == ['111', '222', '333']

    def test_get_scan_channel_list_empty(self, app, test_user):
        """Test empty channel list returns empty list."""
        with app.app_context():
            podcast = create_podcast_with_user(test_user, 'test-podcast-3')

            template = EpisodeGuideTemplate(
                podcast_id=podcast.id,
                name='Test Template'
            )
            db.session.add(template)
            db.session.flush()

            integration = DiscordIntegration(
                template_id=template.id,
                name='Test Discord',
                guild_id='123456789',
                channel_id='111222333',
                scan_channel_ids='',
                scan_emoji='🐭'
            )

            channels = integration.get_scan_channel_list()
            assert channels == []


class TestDiscordIntegrationRoutes:
    """Test Discord integration routes."""

    def test_create_integration_requires_guild_id(self, auth_client, test_user):
        """Test that guild_id is required."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-routes')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/templates/{template.id}/discord',
            json={
                'name': 'Test Discord',
                'channel_ids': '123456789',
                'scan_emoji': '🐭'
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Guild ID' in data['error']

    def test_create_integration_requires_channel_ids(self, auth_client, test_user):
        """Test that at least one channel ID is required."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-routes-2')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/templates/{template.id}/discord',
            json={
                'name': 'Test Discord',
                'guild_id': '123456789',
                'channel_ids': '',
                'scan_emoji': '🐭'
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Channel ID' in data['error']

    def test_create_integration_requires_emoji(self, auth_client, test_user):
        """Test that scan emoji is required."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-routes-3')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/templates/{template.id}/discord',
            json={
                'name': 'Test Discord',
                'guild_id': '123456789',
                'channel_ids': '111222333',
                'scan_emoji': ''
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Emoji' in data['error']

    def test_create_integration_success(self, auth_client, test_user):
        """Test successful integration creation."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-routes-4')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/templates/{template.id}/discord',
            json={
                'name': 'Test Discord',
                'guild_id': '123456789',
                'channel_ids': '111222333,444555666',
                'scan_emoji': '🐭',
                'is_active': True
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['integration']['channel_ids'] == '111222333,444555666'
        assert data['integration']['scan_emoji'] == '🐭'

    def test_get_integration(self, auth_client, test_user):
        """Test fetching existing integration."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-routes-5')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='🐭'
        )
        db.session.add(integration)
        db.session.commit()

        response = auth_client.get(
            f'/podcasts/{podcast.id}/templates/{template.id}/discord'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['integration']['scan_emoji'] == '🐭'


class TestDiscordFetch:
    """Test Discord message fetching."""

    def test_fetch_requires_emoji_configured(self, auth_client, test_user):
        """Test fetch fails if no emoji configured."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-fetch')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='',  # No emoji!
            is_active=True
        )
        db.session.add(integration)
        db.session.flush()

        guide = EpisodeGuide(
            podcast_id=podcast.id,
            template_id=template.id,
            title='Test Episode'
        )
        db.session.add(guide)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/fetch',
            json={'limit': 50}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'emoji' in data['error'].lower()

    @patch('services.discord.DiscordService.get_messages_multi_channel')
    def test_fetch_returns_messages_without_section(self, mock_fetch, auth_client, test_user):
        """Test that fetched messages don't have pre-assigned sections."""
        mock_fetch.return_value = {
            'success': True,
            'messages': [
                {
                    'id': '123',
                    'content': 'Test message',
                    'author': {'username': 'testuser'},
                    'link': 'https://example.com'
                }
            ],
            'channels_scanned': 1,
            'total_channels': 1,
            'errors': []
        }

        podcast = create_podcast_with_user(test_user, 'test-podcast-fetch-2')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='🐭',
            bot_token_env_var='DISCORD_BOT_TOKEN',
            is_active=True
        )
        db.session.add(integration)
        db.session.flush()

        guide = EpisodeGuide(
            podcast_id=podcast.id,
            template_id=template.id,
            title='Test Episode'
        )
        db.session.add(guide)
        db.session.commit()

        with patch.dict('os.environ', {'DISCORD_BOT_TOKEN': 'fake_token'}):
            response = auth_client.post(
                f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/fetch',
                json={'limit': 50}
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'sections' in data  # Should include available sections for selection


class TestDiscordImport:
    """Test Discord message import."""

    def test_import_requires_section(self, auth_client, test_user):
        """Test import fails if no section specified for an item."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-import')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='🐭',
            is_active=True
        )
        db.session.add(integration)
        db.session.flush()

        guide = EpisodeGuide(
            podcast_id=podcast.id,
            template_id=template.id,
            title='Test Episode'
        )
        db.session.add(guide)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/import',
            json={
                'items': [
                    {
                        'discord_message_id': '123',
                        'title': 'Test Topic',
                        'section': '',  # Empty section!
                        'links': []
                    }
                ]
            }
        )

        # Items without valid sections are skipped
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 0  # Should not import without section

    def test_import_with_section_success(self, auth_client, test_user):
        """Test successful import with section specified."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-import-2')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='🐭',
            is_active=True
        )
        db.session.add(integration)
        db.session.flush()

        guide = EpisodeGuide(
            podcast_id=podcast.id,
            template_id=template.id,
            title='Test Episode'
        )
        db.session.add(guide)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/import',
            json={
                'items': [
                    {
                        'discord_message_id': '456',
                        'title': 'New Mouse Release',
                        'section': 'news_mice',
                        'links': ['https://example.com/mouse']
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] == 1

        # Verify item was created
        item = EpisodeGuideItem.query.filter_by(guide_id=guide.id).first()
        assert item is not None
        assert item.title == 'New Mouse Release'
        assert item.section == 'news_mice'

        # Verify import log was created
        log = DiscordImportLog.query.filter_by(discord_message_id='456').first()
        assert log is not None
        assert log.guide_id == guide.id

    def test_import_prevents_duplicates(self, auth_client, test_user):
        """Test that same message can't be imported twice."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-import-3')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='🐭',
            is_active=True
        )
        db.session.add(integration)
        db.session.flush()

        guide = EpisodeGuide(
            podcast_id=podcast.id,
            template_id=template.id,
            title='Test Episode'
        )
        db.session.add(guide)
        db.session.commit()

        # First import
        auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/import',
            json={
                'items': [
                    {
                        'discord_message_id': '789',
                        'title': 'First Import',
                        'section': 'news_mice',
                        'links': []
                    }
                ]
            }
        )

        # Second import with same message ID
        response = auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/import',
            json={
                'items': [
                    {
                        'discord_message_id': '789',
                        'title': 'Duplicate Import',
                        'section': 'news_other',
                        'links': []
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 0  # Should not import duplicate

        # Verify only one item exists
        items = EpisodeGuideItem.query.filter_by(guide_id=guide.id).all()
        assert len(items) == 1
        assert items[0].title == 'First Import'

    def test_skip_message_success(self, auth_client, test_user):
        """Test skipping a message marks it as seen."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-skip')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='🐭',
            is_active=True
        )
        db.session.add(integration)
        db.session.flush()

        guide = EpisodeGuide(
            podcast_id=podcast.id,
            template_id=template.id,
            title='Test Episode'
        )
        db.session.add(guide)
        db.session.commit()

        response = auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/skip',
            json={'discord_message_id': 'skip123'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # Verify skip log was created with no item
        log = DiscordImportLog.query.filter_by(discord_message_id='skip123').first()
        assert log is not None
        assert log.item_id is None  # Skipped, no item created

    def test_skipped_message_not_importable(self, auth_client, test_user):
        """Test that a skipped message cannot be imported."""
        podcast = create_podcast_with_user(test_user, 'test-podcast-skip-2')

        template = EpisodeGuideTemplate(
            podcast_id=podcast.id,
            name='Test Template'
        )
        db.session.add(template)
        db.session.flush()

        integration = DiscordIntegration(
            template_id=template.id,
            name='Test Discord',
            guild_id='123456789',
            channel_id='111222333',
            scan_channel_ids='111222333',
            scan_emoji='🐭',
            is_active=True
        )
        db.session.add(integration)
        db.session.flush()

        guide = EpisodeGuide(
            podcast_id=podcast.id,
            template_id=template.id,
            title='Test Episode'
        )
        db.session.add(guide)
        db.session.commit()

        # First skip the message
        auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/skip',
            json={'discord_message_id': 'skipimport123'}
        )

        # Try to import the same message
        response = auth_client.post(
            f'/podcasts/{podcast.id}/episodes/{guide.id}/discord/import',
            json={
                'items': [
                    {
                        'discord_message_id': 'skipimport123',
                        'title': 'Should Not Import',
                        'section': 'news_mice',
                        'links': []
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 0  # Should not import skipped message

        # Verify no item was created
        items = EpisodeGuideItem.query.filter_by(guide_id=guide.id).all()
        assert len(items) == 0
