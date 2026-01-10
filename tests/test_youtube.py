"""Tests for YouTube API integration."""

import pytest
from unittest.mock import patch, MagicMock
from services.youtube import YouTubeService


class TestYouTubeService:
    """Tests for YouTube service."""

    def test_is_configured_false_without_keys(self, app):
        """Test service reports unconfigured without API keys."""
        with app.app_context():
            app.config['YOUTUBE_API_KEY'] = None
            app.config['YOUTUBE_CHANNEL_ID'] = None
            service = YouTubeService()
            assert service.is_configured is False

    def test_is_configured_true_with_keys(self, app):
        """Test service reports configured with API keys."""
        with app.app_context():
            app.config['YOUTUBE_API_KEY'] = 'test_key'
            app.config['YOUTUBE_CHANNEL_ID'] = 'test_channel'
            service = YouTubeService(api_key='test_key', channel_id='test_channel')
            assert service.is_configured is True

    def test_is_short_detection(self, app):
        """Test YouTube Short detection based on duration."""
        with app.app_context():
            service = YouTubeService()

            # Short (60 seconds or less)
            assert service._is_short('PT45S', 'Test') is True
            assert service._is_short('PT1M', 'Test') is True
            assert service._is_short('PT60S', 'Test') is True

            # Not a Short (over 60 seconds)
            assert service._is_short('PT1M1S', 'Test') is False
            assert service._is_short('PT5M30S', 'Test') is False
            assert service._is_short('PT1H', 'Test') is False

            # Invalid duration
            assert service._is_short('', 'Test') is False
            assert service._is_short(None, 'Test') is False

    def test_get_channel_videos_not_configured(self, app):
        """Test error returned when API not configured."""
        with app.app_context():
            service = YouTubeService(api_key=None, channel_id=None)
            result = service.get_channel_videos()
            assert 'error' in result
            assert result['videos'] == []

    @patch('services.youtube.requests.get')
    def test_get_channel_videos_success(self, mock_get, app):
        """Test fetching videos from channel."""
        with app.app_context():
            # Mock channel response
            channel_response = MagicMock()
            channel_response.json.return_value = {
                'items': [{
                    'contentDetails': {
                        'relatedPlaylists': {'uploads': 'UU123'}
                    }
                }]
            }
            channel_response.raise_for_status = MagicMock()

            # Mock playlist response
            playlist_response = MagicMock()
            playlist_response.json.return_value = {
                'items': [{
                    'contentDetails': {'videoId': 'video123'}
                }],
                'nextPageToken': None
            }
            playlist_response.raise_for_status = MagicMock()

            # Mock video details response
            video_response = MagicMock()
            video_response.json.return_value = {
                'items': [{
                    'id': 'video123',
                    'snippet': {
                        'title': 'Test Video',
                        'description': 'Test description',
                        'publishedAt': '2025-01-10T12:00:00Z',
                        'thumbnails': {'high': {'url': 'https://example.com/thumb.jpg'}}
                    },
                    'statistics': {
                        'viewCount': '1000',
                        'likeCount': '50',
                        'commentCount': '10'
                    },
                    'contentDetails': {
                        'duration': 'PT5M30S'
                    }
                }]
            }
            video_response.raise_for_status = MagicMock()

            mock_get.side_effect = [channel_response, playlist_response, video_response]

            service = YouTubeService(api_key='test_key', channel_id='test_channel')
            result = service.get_channel_videos()

            assert 'error' not in result
            assert len(result['videos']) == 1
            assert result['videos'][0]['title'] == 'Test Video'
            assert result['videos'][0]['views'] == 1000

    @patch('services.youtube.requests.get')
    def test_get_video_details(self, mock_get, app):
        """Test fetching video details."""
        with app.app_context():
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'items': [{
                    'id': 'video123',
                    'snippet': {
                        'title': 'Pulsar X2 Review',
                        'description': 'Review of the Pulsar X2',
                        'publishedAt': '2025-01-10T12:00:00Z',
                        'thumbnails': {'high': {'url': 'https://example.com/thumb.jpg'}}
                    },
                    'statistics': {
                        'viewCount': '5000',
                        'likeCount': '200',
                        'commentCount': '30'
                    },
                    'contentDetails': {
                        'duration': 'PT10M15S'
                    }
                }]
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            service = YouTubeService(api_key='test_key', channel_id='test_channel')
            videos = service.get_video_details(['video123'])

            assert len(videos) == 1
            assert videos[0]['youtube_id'] == 'video123'
            assert videos[0]['title'] == 'Pulsar X2 Review'
            assert videos[0]['views'] == 5000
            assert videos[0]['likes'] == 200
            assert videos[0]['is_short'] is False

    @patch('services.youtube.requests.get')
    def test_refresh_video_stats(self, mock_get, app):
        """Test refreshing video statistics."""
        with app.app_context():
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'items': [{
                    'id': 'video123',
                    'snippet': {
                        'title': 'Test Video',
                        'description': '',
                        'publishedAt': '2025-01-10T12:00:00Z',
                        'thumbnails': {}
                    },
                    'statistics': {
                        'viewCount': '10000',
                        'likeCount': '500',
                    },
                    'contentDetails': {
                        'duration': 'PT5M'
                    }
                }]
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            service = YouTubeService(api_key='test_key', channel_id='test_channel')
            videos = service.refresh_video_stats(['video123'])

            assert len(videos) == 1
            assert videos[0]['views'] == 10000


class TestVideoSyncRoutes:
    """Tests for video sync routes."""

    def test_sync_without_config(self, client, app):
        """Test sync shows error without YouTube config."""
        with app.app_context():
            app.config['YOUTUBE_API_KEY'] = None
            app.config['YOUTUBE_CHANNEL_ID'] = None

        response = client.post('/videos/sync', follow_redirects=True)
        assert response.status_code == 200
        assert b'not configured' in response.data

    def test_refresh_stats_without_config(self, client, app):
        """Test refresh stats shows error without config."""
        with app.app_context():
            app.config['YOUTUBE_API_KEY'] = None
            app.config['YOUTUBE_CHANNEL_ID'] = None

        response = client.post('/videos/refresh-stats', follow_redirects=True)
        assert response.status_code == 200
        assert b'not configured' in response.data

    def test_list_shows_sync_button_when_configured(self, client, app):
        """Test videos list shows sync button when YouTube is configured."""
        with app.app_context():
            app.config['YOUTUBE_API_KEY'] = 'test_key'
            app.config['YOUTUBE_CHANNEL_ID'] = 'test_channel'

        response = client.get('/videos/')
        assert response.status_code == 200
        assert b'Sync from YouTube' in response.data
