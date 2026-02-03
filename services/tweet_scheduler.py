"""Tweet Scheduler service for automated podcast episode tweets.

This service handles:
- Monitoring YouTube channels for live streams
- Generating AI-powered tweets for episodes
- Posting tweets when podcasts go live
- Managing scheduled tweet jobs via APScheduler
"""

import os
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import current_app

from extensions import db
from models import (
    Podcast,
    PodcastMember,
    EpisodeGuide,
    EpisodeTweetConfig,
    SocialConnection,
    SocialPostLog,
)
from services.youtube_live import YouTubeLiveService
from services.social_posting import SocialPostingService, SocialPostingError
from services.content_atomizer import ContentAtomizerService, ContentAtomizerError


class TweetSchedulerError(Exception):
    """Base exception for tweet scheduler errors."""
    pass


class TweetSchedulerService:
    """Service for automated tweet scheduling when podcasts go live."""

    def __init__(self):
        """Initialize the tweet scheduler service."""
        self.youtube_service = YouTubeLiveService()
        self.social_service = SocialPostingService()
        self.atomizer_service = ContentAtomizerService()

    def check_and_post_live_tweets(self):
        """
        Main job: Check all podcasts for live streams and post tweets.

        This method is called by the scheduler every few minutes.
        It checks each podcast's YouTube channel for live status and
        triggers tweets for any pending episode tweet configs.

        Uses ThreadPoolExecutor for concurrent HTTP requests to YouTube.
        """
        # Get all active podcasts with YouTube channels configured
        podcasts = Podcast.query.filter(
            Podcast.is_active == True,
            Podcast.youtube_channel_id.isnot(None),
            Podcast.youtube_channel_id != '',
        ).all()

        if not podcasts:
            return []

        results = []

        # Check podcasts concurrently (up to 10 at once)
        with ThreadPoolExecutor(max_workers=min(10, len(podcasts))) as executor:
            futures = {
                executor.submit(self._check_podcast_live, podcast): podcast
                for podcast in podcasts
            }
            for future in as_completed(futures, timeout=30):
                podcast = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    current_app.logger.error(
                        f'Error checking podcast {podcast.id} ({podcast.name}): {e}'
                    )
                    results.append({
                        'podcast_id': podcast.id,
                        'podcast_name': podcast.name,
                        'error': str(e),
                    })

        return results

    def _check_podcast_live(self, podcast: Podcast) -> dict:
        """
        Check if a specific podcast is live and trigger tweets if so.

        Args:
            podcast: Podcast instance to check

        Returns:
            dict with check results
        """
        result = {
            'podcast_id': podcast.id,
            'podcast_name': podcast.name,
            'is_live': False,
            'video_url': None,
            'video_title': None,
            'tweets_posted': 0,
            'errors': [],
        }

        # Check YouTube live status
        live_status = self.youtube_service.check_channel_live(podcast.youtube_channel_id)

        if live_status.get('error'):
            result['errors'].append(f"YouTube check failed: {live_status['error']}")
            return result

        if not live_status.get('is_live'):
            return result

        result['is_live'] = True
        result['video_url'] = live_status.get('video_url')
        result['video_title'] = live_status.get('video_title')

        # Check title filter if enabled
        if podcast.youtube_title_filter_enabled and podcast.youtube_title_filter:
            video_title = live_status.get('video_title') or ''
            filter_text = podcast.youtube_title_filter

            # Case-insensitive substring match
            if filter_text.lower() not in video_title.lower():
                current_app.logger.info(
                    f'Podcast {podcast.id} ({podcast.name}): Live stream title "{video_title}" '
                    f'does not match filter "{filter_text}", skipping tweet'
                )
                result['errors'].append(
                    f'Title filter not matched: "{video_title}" does not contain "{filter_text}"'
                )
                return result

        # Find the current/upcoming episode for this podcast
        episode = self._get_current_episode(podcast)

        if not episode:
            result['errors'].append('No current episode found')
            return result

        # Update episode URL if not already set
        if not episode.episode_url and live_status.get('video_url'):
            episode.episode_url = live_status['video_url']
            db.session.commit()
            current_app.logger.info(
                f'Updated episode {episode.id} URL to {episode.episode_url}'
            )

        # Get pending tweet configs for this episode with row-level locking
        # to prevent race condition with user disabling their config
        pending_tweets = EpisodeTweetConfig.query.with_for_update().filter(
            EpisodeTweetConfig.episode_id == episode.id,
            EpisodeTweetConfig.status == EpisodeTweetConfig.STATUS_PENDING,
            EpisodeTweetConfig.enabled == True,
        ).all()

        # Post tweets for each host
        for tweet_config in pending_tweets:
            try:
                posted = self._post_tweet_for_host(tweet_config, episode)
                if posted:
                    result['tweets_posted'] += 1
            except Exception as e:
                error_msg = f"Failed to post tweet for user {tweet_config.user_id}: {e}"
                result['errors'].append(error_msg)
                current_app.logger.error(error_msg)

        return result

    def _get_current_episode(self, podcast: Podcast) -> EpisodeGuide | None:
        """
        Get the current or upcoming episode for a podcast.

        Finds the episode that:
        1. Has a scheduled_date of today or within the last 24 hours
        2. Is not yet marked as completed
        3. Has pending tweet configs

        Args:
            podcast: Podcast to get episode for

        Returns:
            EpisodeGuide or None
        """
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)

        # Find episode scheduled for today or yesterday (in case stream started late)
        episode = EpisodeGuide.query.filter(
            EpisodeGuide.podcast_id == podcast.id,
            EpisodeGuide.scheduled_date >= yesterday,
            EpisodeGuide.scheduled_date <= today,
        ).order_by(EpisodeGuide.scheduled_date.desc()).first()

        return episode

    def post_tweet_for_user(
        self, user_id: int, episode_id: int, connection: SocialConnection | None = None
    ) -> dict:
        """
        Post a tweet for a specific user. Used by both scheduler and manual posting.

        Args:
            user_id: The user's ID
            episode_id: The episode to tweet about
            connection: Optional pre-fetched Twitter connection

        Returns:
            dict with 'success', 'error', 'tweet_url', etc.
        """
        # Get config with row-level locking to prevent duplicate posts
        config = EpisodeTweetConfig.query.filter_by(
            episode_id=episode_id, user_id=user_id
        ).with_for_update().first()

        if not config:
            return {'success': False, 'error': 'No tweet configuration found'}

        if config.status == EpisodeTweetConfig.STATUS_POSTED:
            return {'success': False, 'error': 'Tweet already posted', 'tweet_url': config.tweet_url}

        # Get Twitter connection if not provided
        if not connection:
            connection = self.social_service.get_user_connection(user_id, 'twitter')

        if not connection:
            config.status = EpisodeTweetConfig.STATUS_FAILED
            config.error_message = 'No Twitter account connected'
            db.session.commit()
            return {'success': False, 'error': 'No Twitter account connected'}

        # Get episode
        episode = config.episode
        if not episode:
            return {'success': False, 'error': 'Episode not found'}

        # Build content
        content = config.content
        if not content:
            content = episode.title
            if config.include_url and episode.episode_url:
                content = f"{content}\n\n{episode.episode_url}"

        if not content:
            return {'success': False, 'error': 'No content to post'}

        # Ensure content fits Twitter limit (280 chars)
        if len(content) > 280:
            if config.include_url and episode.episode_url:
                url_len = len(episode.episode_url) + 4
                max_text = 280 - url_len
                content = content[:max_text-3] + '...'
                content = f"{content}\n\n{episode.episode_url}"
            else:
                content = content[:277] + '...'

        # Post the tweet
        try:
            result = self.social_service.post_to_twitter(connection, content)

            if result.get('success'):
                config.status = EpisodeTweetConfig.STATUS_POSTED
                config.posted_at = datetime.now(timezone.utc)
                config.tweet_id = result.get('tweet_id')
                config.tweet_url = result.get('tweet_url')
                config.error_message = None

                # Log the post
                log = SocialPostLog(
                    user_id=user_id,
                    connection_id=connection.id,
                    platform='twitter',
                    content_posted=content,
                    success=True,
                    platform_post_id=result.get('tweet_id'),
                    platform_post_url=result.get('tweet_url'),
                    response_time_ms=result.get('response_time_ms'),
                )
                db.session.add(log)
                db.session.commit()

                current_app.logger.info(
                    f'Posted tweet for user {user_id}, episode {episode.id}: {result.get("tweet_url")}'
                )
                return {
                    'success': True,
                    'tweet_url': result.get('tweet_url'),
                    'tweet_id': result.get('tweet_id'),
                }
            else:
                config.status = EpisodeTweetConfig.STATUS_FAILED
                config.error_message = result.get('error', 'Unknown error')
                config.retry_count += 1
                db.session.commit()

                current_app.logger.warning(
                    f'Failed to post tweet for user {user_id}: {result.get("error")}'
                )
                return {'success': False, 'error': result.get('error', 'Failed to post tweet')}

        except SocialPostingError as e:
            db.session.rollback()

            # Re-fetch and update status in clean session
            config = EpisodeTweetConfig.query.filter_by(
                episode_id=episode_id, user_id=user_id
            ).first()
            if config:
                config.status = EpisodeTweetConfig.STATUS_FAILED
                config.error_message = str(e)[:500]
                config.retry_count += 1
                db.session.commit()

            raise

    def _post_tweet_for_host(self, tweet_config: EpisodeTweetConfig, episode: EpisodeGuide) -> bool:
        """
        Post a tweet for a specific host.

        Args:
            tweet_config: EpisodeTweetConfig for the host
            episode: EpisodeGuide being tweeted about

        Returns:
            True if posted successfully, False otherwise
        """
        user_id = tweet_config.user_id

        # Check if user has Twitter connected
        connection = self.social_service.get_user_connection(user_id, 'twitter')

        if not connection:
            tweet_config.status = EpisodeTweetConfig.STATUS_FAILED
            tweet_config.error_message = 'No Twitter account connected'
            db.session.commit()
            return False

        # Generate content if not already set
        if not tweet_config.content:
            content = self._generate_tweet_content(tweet_config, episode)
            if content:
                tweet_config.generated_content = content
                db.session.commit()

        # Get final content
        content = tweet_config.content
        if not content:
            # Fallback: just title and URL
            content = episode.title
            if tweet_config.include_url and episode.episode_url:
                content = f"{content}\n\n{episode.episode_url}"

        # Ensure content fits Twitter limit (280 chars)
        if len(content) > 280:
            # Truncate content, leaving room for URL if needed
            if tweet_config.include_url and episode.episode_url:
                url_len = len(episode.episode_url) + 4  # +4 for newlines
                max_text = 280 - url_len
                content = content[:max_text-3] + '...'
                content = f"{content}\n\n{episode.episode_url}"
            else:
                content = content[:277] + '...'

        # Post the tweet
        try:
            result = self.social_service.post_to_twitter(connection, content)

            if result.get('success'):
                tweet_config.status = EpisodeTweetConfig.STATUS_POSTED
                tweet_config.posted_at = datetime.now(timezone.utc)
                tweet_config.tweet_id = result.get('tweet_id')
                tweet_config.tweet_url = result.get('tweet_url')
                tweet_config.error_message = None

                # Log the post
                log = SocialPostLog(
                    user_id=user_id,
                    connection_id=connection.id,
                    platform='twitter',
                    content_posted=content,
                    success=True,
                    platform_post_id=result.get('tweet_id'),
                    platform_post_url=result.get('tweet_url'),
                    response_time_ms=result.get('response_time_ms'),
                )
                db.session.add(log)
                db.session.commit()

                current_app.logger.info(
                    f'Posted tweet for user {user_id}, episode {episode.id}: {result.get("tweet_url")}'
                )
                return True
            else:
                tweet_config.status = EpisodeTweetConfig.STATUS_FAILED
                tweet_config.error_message = result.get('error', 'Unknown error')
                tweet_config.retry_count += 1
                db.session.commit()

                current_app.logger.warning(
                    f'Failed to post tweet for user {user_id}: {result.get("error")}'
                )
                return False

        except SocialPostingError as e:
            tweet_config.status = EpisodeTweetConfig.STATUS_FAILED
            tweet_config.error_message = str(e)
            tweet_config.retry_count += 1
            db.session.commit()
            raise

    def _generate_tweet_content(self, tweet_config: EpisodeTweetConfig, episode: EpisodeGuide) -> str | None:
        """
        Generate AI-powered tweet content for an episode.

        Args:
            tweet_config: EpisodeTweetConfig instance
            episode: EpisodeGuide to generate tweet for

        Returns:
            Generated tweet text or None if generation fails
        """
        try:
            # Get episode content for AI
            source_data = self.atomizer_service.get_source_content_from_episode(episode.id)
            source_content = source_data.get('content', '')

            if not source_content:
                source_content = episode.title

            # Generate tweet via AI
            result = self.atomizer_service.generate(
                source_content=source_content,
                platform='twitter',
                options={
                    'include_hashtags': True,
                    'include_cta': True,
                    'tone': 'excited, engaging',
                }
            )

            generated_content = result.get('content', '')

            # Append URL if configured and we have room
            if tweet_config.include_url and episode.episode_url:
                url_addition = f"\n\n{episode.episode_url}"
                if len(generated_content) + len(url_addition) <= 280:
                    generated_content += url_addition

            return generated_content

        except ContentAtomizerError as e:
            current_app.logger.warning(f'AI content generation failed: {e}')
            return None
        except Exception as e:
            current_app.logger.error(f'Unexpected error generating tweet: {e}')
            return None

    def generate_tweet_content(
        self, config: EpisodeTweetConfig, episode: EpisodeGuide
    ) -> str | None:
        """
        Generate AI-powered tweet content for a specific config.

        Public wrapper for external callers (e.g., route handlers).

        Args:
            config: The tweet config to generate content for
            episode: The episode being tweeted about

        Returns:
            Generated content string or None if generation fails
        """
        return self._generate_tweet_content(config, episode)

    def create_tweet_configs_for_episode(
        self, episode: EpisodeGuide, generate_content: bool = True
    ) -> list[EpisodeTweetConfig]:
        """
        Create tweet configs for all hosts of an episode's podcast.

        Called when an episode is created or scheduled.

        Args:
            episode: EpisodeGuide to create configs for
            generate_content: Whether to generate AI content immediately

        Returns:
            List of created EpisodeTweetConfig instances
        """
        if not episode.podcast_id:
            return []

        # Get all members of the podcast
        members = PodcastMember.query.filter_by(podcast_id=episode.podcast_id).all()

        if not members:
            return []

        # Batch-fetch existing configs to avoid N+1 queries
        member_user_ids = [m.user_id for m in members]
        existing_configs = {
            c.user_id: c
            for c in EpisodeTweetConfig.query.filter(
                EpisodeTweetConfig.episode_id == episode.id,
                EpisodeTweetConfig.user_id.in_(member_user_ids)
            ).all()
        }

        configs = []

        for member in members:
            # Check if config already exists (from batch query)
            existing = existing_configs.get(member.user_id)
            if existing:
                configs.append(existing)
                continue

            # Create new config
            config = EpisodeTweetConfig(
                episode_id=episode.id,
                user_id=member.user_id,
                enabled=True,
                include_url=True,
                status=EpisodeTweetConfig.STATUS_PENDING,
            )

            # Generate content if requested
            if generate_content:
                content = self._generate_tweet_content(config, episode)
                if content:
                    config.generated_content = content

            db.session.add(config)
            configs.append(config)

        db.session.commit()
        return configs
