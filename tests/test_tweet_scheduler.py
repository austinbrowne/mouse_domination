"""Tests for Tweet Scheduler: YouTube live detection and automated tweets.

Tests cover:
- YouTubeLiveService (live detection logic)
- TweetSchedulerService (tweet generation and posting)
- EpisodeTweetConfig model operations
- Integration with existing social posting infrastructure
"""

import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import Mock, patch, MagicMock

from app import create_app
from extensions import db
from models import (
    User, Podcast, PodcastMember, EpisodeGuide, EpisodeTweetConfig,
    SocialConnection, SocialPostLog
)
from config import TestConfig


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def test_user(app):
    """Create an approved test user."""
    with app.app_context():
        user = User(
            email='host1@example.com',
            name='Host One',
            is_approved=True,
            is_admin=False
        )
        user.set_password('TestPassword123!')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {'id': user_id, 'email': 'host1@example.com', 'password': 'TestPassword123!'}


@pytest.fixture
def second_user(app):
    """Create a second test user (second host)."""
    with app.app_context():
        user = User(
            email='host2@example.com',
            name='Host Two',
            is_approved=True,
            is_admin=False
        )
        user.set_password('TestPassword123!')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {'id': user_id, 'email': 'host2@example.com', 'password': 'TestPassword123!'}


@pytest.fixture
def podcast_with_youtube(app, test_user):
    """Create a podcast with YouTube channel configured."""
    with app.app_context():
        podcast = Podcast(
            name='Test Podcast',
            slug='test-podcast',
            description='A test podcast',
            youtube_channel_id='UCxxxxxxxxxxxxxxxx1234',
            created_by=test_user['id'],
            is_active=True
        )
        db.session.add(podcast)
        db.session.commit()

        # Add user as admin member
        member = PodcastMember(
            podcast_id=podcast.id,
            user_id=test_user['id'],
            role='admin'
        )
        db.session.add(member)
        db.session.commit()

        podcast_id = podcast.id
    return {'id': podcast_id, 'youtube_channel_id': 'UCxxxxxxxxxxxxxxxx1234'}


@pytest.fixture
def episode_today(app, podcast_with_youtube):
    """Create an episode scheduled for today."""
    with app.app_context():
        episode = EpisodeGuide(
            title='Episode 100: Test Episode',
            episode_number=100,
            scheduled_date=date.today(),
            podcast_id=podcast_with_youtube['id'],
            status='draft',
            notes='This is a test episode about Python programming.'
        )
        db.session.add(episode)
        db.session.commit()
        episode_id = episode.id
    return {'id': episode_id, 'title': 'Episode 100: Test Episode'}


@pytest.fixture
def twitter_connection(app, test_user):
    """Create a Twitter connection for the test user."""
    with app.app_context():
        # Mock encrypted credentials
        connection = SocialConnection(
            user_id=test_user['id'],
            platform='twitter',
            platform_user_id='123456789',
            platform_username='testhost',
            encrypted_credentials='mock_encrypted_creds',
            is_active=True,
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
        )
        db.session.add(connection)
        db.session.commit()
        connection_id = connection.id
    return {'id': connection_id, 'user_id': test_user['id']}


# =============================================================================
# YouTube Live Service Tests
# =============================================================================

class TestYouTubeLiveService:
    """Tests for YouTubeLiveService."""

    def test_check_channel_live_when_live(self, app):
        """Test detecting a live stream."""
        with app.app_context():
            from services.youtube_live import YouTubeLiveService

            service = YouTubeLiveService()

            # Mock the requests to simulate a live channel
            with patch('services.youtube_live.requests') as mock_requests:
                # Simulate redirect to a video
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {'Location': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}
                mock_requests.head.return_value = mock_response

                result = service.check_channel_live('UCxxxxxxxxxxxxxxxx1234')

                assert result['is_live'] is True
                assert result['video_id'] == 'dQw4w9WgXcQ'
                assert result['video_url'] == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
                assert result['error'] is None

    def test_check_channel_live_when_not_live(self, app):
        """Test when channel is not streaming."""
        with app.app_context():
            from services.youtube_live import YouTubeLiveService

            service = YouTubeLiveService()

            # Mock the requests to simulate no live stream
            with patch('services.youtube_live.requests') as mock_requests:
                # First HEAD request returns 200 (no redirect)
                mock_head = Mock()
                mock_head.status_code = 200
                mock_requests.head.return_value = mock_head

                # GET request returns channel page (not a video)
                mock_get = Mock()
                mock_get.status_code = 200
                mock_get.url = 'https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxx1234'
                mock_get.text = '<html>Channel page content</html>'
                mock_requests.get.return_value = mock_get

                result = service.check_channel_live('UCxxxxxxxxxxxxxxxx1234')

                assert result['is_live'] is False
                assert result['video_id'] is None
                assert result['video_url'] is None

    def test_check_channel_live_no_channel_id(self, app):
        """Test with empty channel ID."""
        with app.app_context():
            from services.youtube_live import YouTubeLiveService

            service = YouTubeLiveService()
            result = service.check_channel_live('')

            assert result['is_live'] is False
            assert result['error'] == 'No channel ID provided'

    def test_check_channel_live_timeout(self, app):
        """Test handling request timeout."""
        with app.app_context():
            from services.youtube_live import YouTubeLiveService
            import requests

            service = YouTubeLiveService()

            with patch('services.youtube_live.requests') as mock_requests:
                mock_requests.head.side_effect = requests.Timeout()
                mock_requests.Timeout = requests.Timeout

                result = service.check_channel_live('UCxxxxxxxxxxxxxxxx1234')

                assert result['is_live'] is False
                assert result['error'] == 'Request timed out'

    def test_extract_video_id_various_formats(self, app):
        """Test video ID extraction from various URL formats."""
        with app.app_context():
            from services.youtube_live import YouTubeLiveService

            service = YouTubeLiveService()

            # Standard watch URL
            assert service._extract_video_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ') == 'dQw4w9WgXcQ'

            # Short URL
            assert service._extract_video_id('https://youtu.be/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'

            # With additional params
            assert service._extract_video_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120') == 'dQw4w9WgXcQ'

            # Invalid URL
            assert service._extract_video_id('https://www.youtube.com/channel/UC123') is None


# =============================================================================
# EpisodeTweetConfig Model Tests
# =============================================================================

class TestEpisodeTweetConfigModel:
    """Tests for EpisodeTweetConfig model."""

    def test_create_tweet_config(self, app, episode_today, test_user):
        """Test creating a tweet configuration."""
        with app.app_context():
            config = EpisodeTweetConfig(
                episode_id=episode_today['id'],
                user_id=test_user['id'],
                enabled=True,
                include_url=True,
                generated_content='Check out our new episode!',
                status=EpisodeTweetConfig.STATUS_PENDING
            )
            db.session.add(config)
            db.session.commit()

            retrieved = EpisodeTweetConfig.query.filter_by(
                episode_id=episode_today['id'],
                user_id=test_user['id']
            ).first()

            assert retrieved is not None
            assert retrieved.enabled is True
            assert retrieved.content == 'Check out our new episode!'
            assert retrieved.status == 'pending'

    def test_custom_content_overrides_generated(self, app, episode_today, test_user):
        """Test that custom_content takes precedence over generated_content."""
        with app.app_context():
            config = EpisodeTweetConfig(
                episode_id=episode_today['id'],
                user_id=test_user['id'],
                generated_content='AI generated tweet',
                custom_content='My custom tweet'
            )
            db.session.add(config)
            db.session.commit()

            assert config.content == 'My custom tweet'

    def test_unique_constraint_per_episode_user(self, app, episode_today, test_user):
        """Test unique constraint on episode_id + user_id."""
        with app.app_context():
            config1 = EpisodeTweetConfig(
                episode_id=episode_today['id'],
                user_id=test_user['id'],
                enabled=True
            )
            db.session.add(config1)
            db.session.commit()

            # Try to create duplicate
            config2 = EpisodeTweetConfig(
                episode_id=episode_today['id'],
                user_id=test_user['id'],
                enabled=False
            )
            db.session.add(config2)

            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()

    def test_to_dict(self, app, episode_today, test_user):
        """Test to_dict serialization."""
        with app.app_context():
            config = EpisodeTweetConfig(
                episode_id=episode_today['id'],
                user_id=test_user['id'],
                generated_content='Test tweet',
                enabled=True,
                include_url=True,
                status=EpisodeTweetConfig.STATUS_PENDING
            )
            db.session.add(config)
            db.session.commit()

            # Reload to get relationships
            config = EpisodeTweetConfig.query.get(config.id)
            data = config.to_dict()

            assert data['episode_id'] == episode_today['id']
            assert data['user_id'] == test_user['id']
            assert data['content'] == 'Test tweet'
            assert data['enabled'] is True
            assert data['status'] == 'pending'


# =============================================================================
# Tweet Scheduler Service Tests
# =============================================================================

class TestTweetSchedulerService:
    """Tests for TweetSchedulerService."""

    def test_create_tweet_configs_for_episode(self, app, episode_today, test_user, second_user, podcast_with_youtube):
        """Test creating tweet configs for all podcast members."""
        with app.app_context():
            # Add second user as member
            member = PodcastMember(
                podcast_id=podcast_with_youtube['id'],
                user_id=second_user['id'],
                role='contributor'
            )
            db.session.add(member)
            db.session.commit()

            from services.tweet_scheduler import TweetSchedulerService

            service = TweetSchedulerService()
            episode = EpisodeGuide.query.get(episode_today['id'])

            # Mock AI generation to avoid API calls
            with patch.object(service, '_generate_tweet_content', return_value='Generated tweet content'):
                configs = service.create_tweet_configs_for_episode(episode, generate_content=True)

            assert len(configs) == 2  # Both members get configs

            # Verify configs were created for both users
            user_ids = {c.user_id for c in configs}
            assert test_user['id'] in user_ids
            assert second_user['id'] in user_ids

    def test_get_current_episode(self, app, episode_today, podcast_with_youtube):
        """Test finding the current episode for a podcast."""
        with app.app_context():
            from services.tweet_scheduler import TweetSchedulerService

            service = TweetSchedulerService()
            podcast = Podcast.query.get(podcast_with_youtube['id'])

            episode = service._get_current_episode(podcast)

            assert episode is not None
            assert episode.id == episode_today['id']

    def test_get_current_episode_none_scheduled(self, app, podcast_with_youtube):
        """Test when no episode is scheduled for today."""
        with app.app_context():
            from services.tweet_scheduler import TweetSchedulerService

            # Create episode for next week
            episode = EpisodeGuide(
                title='Future Episode',
                scheduled_date=date.today() + timedelta(days=7),
                podcast_id=podcast_with_youtube['id'],
                status='draft'
            )
            db.session.add(episode)
            db.session.commit()

            service = TweetSchedulerService()
            podcast = Podcast.query.get(podcast_with_youtube['id'])

            current = service._get_current_episode(podcast)

            assert current is None

    def test_check_podcast_live_posts_tweets(self, app, episode_today, test_user, podcast_with_youtube, twitter_connection):
        """Test that tweets are posted when podcast goes live."""
        with app.app_context():
            from services.tweet_scheduler import TweetSchedulerService

            # Create tweet config
            config = EpisodeTweetConfig(
                episode_id=episode_today['id'],
                user_id=test_user['id'],
                generated_content='We are LIVE! Check out the stream!',
                enabled=True,
                include_url=True,
                status=EpisodeTweetConfig.STATUS_PENDING
            )
            db.session.add(config)
            db.session.commit()

            service = TweetSchedulerService()
            podcast = Podcast.query.get(podcast_with_youtube['id'])

            # Mock YouTube live check to return live
            with patch.object(service.youtube_service, 'check_channel_live') as mock_live:
                mock_live.return_value = {
                    'is_live': True,
                    'video_id': 'abc123',
                    'video_url': 'https://www.youtube.com/watch?v=abc123',
                    'error': None
                }

                # Mock Twitter posting
                with patch.object(service.social_service, 'post_to_twitter') as mock_post:
                    mock_post.return_value = {
                        'success': True,
                        'tweet_id': '1234567890',
                        'tweet_url': 'https://twitter.com/testhost/status/1234567890',
                        'response_time_ms': 150
                    }

                    # Mock get_user_connection to return the connection
                    with patch.object(service.social_service, 'get_user_connection') as mock_conn:
                        mock_conn.return_value = SocialConnection.query.get(twitter_connection['id'])

                        result = service._check_podcast_live(podcast)

            assert result['is_live'] is True
            assert result['tweets_posted'] == 1

            # Verify config was updated
            config = EpisodeTweetConfig.query.filter_by(
                episode_id=episode_today['id'],
                user_id=test_user['id']
            ).first()
            assert config.status == EpisodeTweetConfig.STATUS_POSTED
            assert config.tweet_url == 'https://twitter.com/testhost/status/1234567890'

    def test_fallback_content_when_ai_fails(self, app, episode_today, test_user, podcast_with_youtube, twitter_connection):
        """Test fallback to episode title when AI generation fails."""
        with app.app_context():
            from services.tweet_scheduler import TweetSchedulerService

            # Create config with no content (AI failed)
            config = EpisodeTweetConfig(
                episode_id=episode_today['id'],
                user_id=test_user['id'],
                generated_content=None,
                custom_content=None,
                enabled=True,
                include_url=True,
                status=EpisodeTweetConfig.STATUS_PENDING
            )
            db.session.add(config)

            # Set episode URL
            episode = EpisodeGuide.query.get(episode_today['id'])
            episode.episode_url = 'https://www.youtube.com/watch?v=abc123'
            db.session.commit()

            service = TweetSchedulerService()

            with patch.object(service.social_service, 'post_to_twitter') as mock_post:
                mock_post.return_value = {
                    'success': True,
                    'tweet_id': '1234567890',
                    'tweet_url': 'https://twitter.com/testhost/status/1234567890'
                }

                with patch.object(service.social_service, 'get_user_connection') as mock_conn:
                    mock_conn.return_value = SocialConnection.query.get(twitter_connection['id'])

                    service._post_tweet_for_host(config, episode)

            # Check that the fallback content was used (title + URL)
            call_args = mock_post.call_args
            posted_content = call_args[0][1]  # Second positional arg is content
            assert 'Episode 100: Test Episode' in posted_content
            assert 'https://www.youtube.com/watch?v=abc123' in posted_content


# =============================================================================
# Podcast Model Tests (YouTube field)
# =============================================================================

class TestPodcastYouTubeField:
    """Tests for youtube_channel_id field on Podcast model."""

    def test_youtube_channel_id_stored(self, app, test_user):
        """Test that youtube_channel_id is stored correctly."""
        with app.app_context():
            podcast = Podcast(
                name='YouTube Podcast',
                slug='youtube-podcast',
                youtube_channel_id='UCabcdefghij1234567890',
                created_by=test_user['id']
            )
            db.session.add(podcast)
            db.session.commit()

            retrieved = Podcast.query.filter_by(slug='youtube-podcast').first()
            assert retrieved.youtube_channel_id == 'UCabcdefghij1234567890'

    def test_youtube_channel_id_in_to_dict(self, app, test_user):
        """Test that youtube_channel_id is included in to_dict."""
        with app.app_context():
            podcast = Podcast(
                name='YouTube Podcast',
                slug='youtube-podcast',
                youtube_channel_id='UCabcdefghij1234567890',
                created_by=test_user['id']
            )
            db.session.add(podcast)
            db.session.commit()

            data = podcast.to_dict()
            assert data['youtube_channel_id'] == 'UCabcdefghij1234567890'
