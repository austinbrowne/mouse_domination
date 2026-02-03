"""YouTube Live Detection service.

Detects when a YouTube channel goes live by checking the /live redirect.
This approach uses no API quota - just a simple HTTP request.
"""

import re
import requests
from datetime import datetime, timezone
from flask import current_app


class YouTubeLiveError(Exception):
    """Base exception for YouTube live detection errors."""
    pass


class YouTubeLiveService:
    """Service for detecting live YouTube streams."""

    # YouTube channel live URL pattern
    LIVE_URL_TEMPLATE = 'https://www.youtube.com/channel/{channel_id}/live'

    # Regex to extract video ID from YouTube URLs
    VIDEO_ID_PATTERN = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})')

    def __init__(self, timeout=10):
        """
        Initialize the YouTube live detection service.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout

    def check_channel_live(self, channel_id: str) -> dict:
        """
        Check if a YouTube channel is currently live.

        Uses the /live redirect approach:
        - If live: redirects to youtube.com/watch?v=VIDEO_ID
        - If not live: redirects to channel page or shows "no live" page

        Args:
            channel_id: YouTube channel ID (e.g., UCxxxxxx)

        Returns:
            dict with:
                - is_live: bool
                - video_id: str or None
                - video_url: str or None
                - video_title: str or None
                - error: str or None
        """
        if not channel_id:
            return {
                'is_live': False,
                'video_id': None,
                'video_url': None,
                'video_title': None,
                'error': 'No channel ID provided',
            }

        live_url = self.LIVE_URL_TEMPLATE.format(channel_id=channel_id)

        try:
            # Use HEAD request first to check redirect without downloading full page
            # allow_redirects=False lets us inspect the redirect URL
            response = requests.head(
                live_url,
                allow_redirects=False,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; PodcastBot/1.0)',
                }
            )

            # Check for redirect
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location', '')

                # Extract video ID from redirect URL
                video_id = self._extract_video_id(redirect_url)

                if video_id:
                    # Follow redirect with GET to verify live status AND get title in one request
                    video_response = requests.get(
                        redirect_url,
                        timeout=self.timeout,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (compatible; PodcastBot/1.0)',
                        }
                    )

                    # Verify it's actually live AND extract title from same response
                    if self._is_live_page(video_response.text):
                        video_title = self._extract_title_from_html(video_response.text)
                        return {
                            'is_live': True,
                            'video_id': video_id,
                            'video_url': f'https://www.youtube.com/watch?v={video_id}',
                            'video_title': video_title,
                            'error': None,
                        }

            # If no redirect or redirect isn't to a video, try GET request
            # to check page content for live indicators
            response = requests.get(
                live_url,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; PodcastBot/1.0)',
                }
            )

            # Check final URL after redirects
            final_url = response.url
            video_id = self._extract_video_id(final_url)

            if video_id:
                # Verify it's actually live by checking page content
                if self._is_live_page(response.text):
                    video_title = self._extract_title_from_html(response.text)
                    return {
                        'is_live': True,
                        'video_id': video_id,
                        'video_url': f'https://www.youtube.com/watch?v={video_id}',
                        'video_title': video_title,
                        'error': None,
                    }

            # Not live
            return {
                'is_live': False,
                'video_id': None,
                'video_url': None,
                'video_title': None,
                'error': None,
            }

        except requests.Timeout:
            return {
                'is_live': False,
                'video_id': None,
                'video_url': None,
                'video_title': None,
                'error': 'Request timed out',
            }
        except requests.ConnectionError:
            return {
                'is_live': False,
                'video_id': None,
                'video_url': None,
                'video_title': None,
                'error': 'Connection failed',
            }
        except Exception as e:
            current_app.logger.error(f'YouTube live check error: {e}')
            return {
                'is_live': False,
                'video_id': None,
                'video_url': None,
                'video_title': None,
                'error': str(e),
            }

    def _extract_video_id(self, url: str) -> str | None:
        """Extract YouTube video ID from a URL."""
        if not url:
            return None

        match = self.VIDEO_ID_PATTERN.search(url)
        if match:
            return match.group(1)

        # Also check for /live/ URLs that might contain video ID
        if '/watch?v=' in url:
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'v' in params:
                    return params['v'][0]
            except Exception:
                pass

        return None

    def _is_live_page(self, html: str) -> bool:
        """
        Check if the page HTML indicates a live stream.

        Looks for live stream indicators in the page content.
        """
        if not html:
            return False

        # Common indicators that a stream is live
        live_indicators = [
            '"isLive":true',
            '"isLiveNow":true',
            'hqdefault_live.jpg',
            '"liveBroadcastDetails"',
            '"isLiveBroadcast":true',
        ]

        html_lower = html.lower() if html else ''

        for indicator in live_indicators:
            if indicator.lower() in html_lower:
                return True

        return False

    def _extract_title_from_html(self, html: str) -> str | None:
        """
        Extract video title from YouTube page HTML.

        Args:
            html: The page HTML content

        Returns:
            Video title or None if not found
        """
        if not html:
            return None

        # Try multiple patterns to find the title
        patterns = [
            # Pattern in YouTube's embedded JSON data
            r'"title":\s*\{\s*"runs":\s*\[\s*\{\s*"text":\s*"([^"]+)"',
            # Simpler pattern for title field
            r'"title":\s*"([^"]+)"',
            # og:title meta tag
            r'<meta\s+property="og:title"\s+content="([^"]+)"',
            # Title tag
            r'<title>([^<]+)</title>',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                title = match.group(1)
                # Clean up escaped characters
                title = title.replace('\\u0026', '&')
                title = title.replace('\\u0027', "'")
                title = title.replace('\\n', ' ')
                title = title.replace('\\', '')
                # Remove " - YouTube" suffix if present
                if title.endswith(' - YouTube'):
                    title = title[:-10]
                return title.strip()

        return None

    def _fetch_video_title(self, video_id: str) -> str | None:
        """
        Fetch video title by requesting the video page.

        Args:
            video_id: YouTube video ID

        Returns:
            Video title or None if request fails
        """
        try:
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            response = requests.get(
                video_url,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; PodcastBot/1.0)',
                }
            )
            if response.status_code == 200:
                return self._extract_title_from_html(response.text)
        except Exception as e:
            current_app.logger.warning(f'Failed to fetch video title: {e}')

        return None
