"""YouTube Data API integration for fetching channel videos."""

import requests
from datetime import datetime
from flask import current_app


class YouTubeService:
    """Service for interacting with YouTube Data API v3."""

    BASE_URL = 'https://www.googleapis.com/youtube/v3'

    def __init__(self, api_key=None, channel_id=None):
        self.api_key = api_key or current_app.config.get('YOUTUBE_API_KEY')
        self.channel_id = channel_id or current_app.config.get('YOUTUBE_CHANNEL_ID')

    @property
    def is_configured(self):
        """Check if YouTube API is configured."""
        return bool(self.api_key and self.channel_id)

    def get_channel_videos(self, max_results=50, page_token=None):
        """
        Fetch videos from the channel's uploads playlist.

        Args:
            max_results: Number of videos to fetch (max 50 per request)
            page_token: Token for pagination

        Returns:
            dict with 'videos' list and 'next_page_token'
        """
        if not self.is_configured:
            return {'error': 'YouTube API not configured', 'videos': []}

        # First, get the uploads playlist ID
        channel_url = f"{self.BASE_URL}/channels"
        channel_params = {
            'key': self.api_key,
            'id': self.channel_id,
            'part': 'contentDetails',
        }

        try:
            resp = requests.get(channel_url, params=channel_params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data.get('items'):
                return {'error': 'Channel not found', 'videos': []}

            uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # Now fetch videos from the uploads playlist
            playlist_url = f"{self.BASE_URL}/playlistItems"
            playlist_params = {
                'key': self.api_key,
                'playlistId': uploads_playlist_id,
                'part': 'snippet,contentDetails',
                'maxResults': min(max_results, 50),
            }
            if page_token:
                playlist_params['pageToken'] = page_token

            resp = requests.get(playlist_url, params=playlist_params, timeout=10)
            resp.raise_for_status()
            playlist_data = resp.json()

            # Extract video IDs to get full statistics
            video_ids = [item['contentDetails']['videoId'] for item in playlist_data.get('items', [])]

            if not video_ids:
                return {'videos': [], 'next_page_token': None}

            # Get full video details including stats
            videos = self.get_video_details(video_ids)

            return {
                'videos': videos,
                'next_page_token': playlist_data.get('nextPageToken'),
            }

        except requests.RequestException as e:
            return {'error': str(e), 'videos': []}

    def get_video_details(self, video_ids):
        """
        Get detailed info for specific videos.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            List of video data dicts
        """
        if not self.api_key:
            return []

        if isinstance(video_ids, str):
            video_ids = [video_ids]

        videos_url = f"{self.BASE_URL}/videos"
        params = {
            'key': self.api_key,
            'id': ','.join(video_ids),
            'part': 'snippet,contentDetails,statistics',
        }

        try:
            resp = requests.get(videos_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            videos = []
            for item in data.get('items', []):
                snippet = item['snippet']
                stats = item.get('statistics', {})
                content = item.get('contentDetails', {})

                # Parse publish date
                publish_date = None
                if snippet.get('publishedAt'):
                    publish_date = datetime.fromisoformat(
                        snippet['publishedAt'].replace('Z', '+00:00')
                    ).date()

                # Detect if it's a Short (duration <= 60 seconds, vertical)
                duration = content.get('duration', '')
                is_short = self._is_short(duration, snippet.get('title', ''))

                videos.append({
                    'youtube_id': item['id'],
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', ''),
                    'url': f"https://www.youtube.com/watch?v={item['id']}",
                    'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url'),
                    'publish_date': publish_date,
                    'duration': duration,
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)) if stats.get('likeCount') else None,
                    'comments': int(stats.get('commentCount', 0)) if stats.get('commentCount') else None,
                    'is_short': is_short,
                })

            return videos

        except requests.RequestException:
            return []

    def _is_short(self, duration, title):
        """Detect if video is a YouTube Short based on duration."""
        if not duration:
            return False

        # Parse ISO 8601 duration (PT1M30S = 1 min 30 sec)
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return False

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        total_seconds = hours * 3600 + minutes * 60 + seconds

        # Shorts are <= 60 seconds
        return total_seconds <= 60

    def refresh_video_stats(self, video_ids):
        """
        Refresh view counts and stats for existing videos.

        Args:
            video_ids: List of YouTube video IDs to refresh

        Returns:
            List of updated video data
        """
        return self.get_video_details(video_ids)
