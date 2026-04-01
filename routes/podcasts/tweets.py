"""Tweet configuration routes for episode automation.

These routes allow podcast hosts to:
- View and edit their tweet configurations per episode
- Generate AI-powered tweet content
- Enable/disable automatic tweeting
- Preview how tweets will appear
"""
from flask import render_template, request, redirect, url_for, flash, g, jsonify
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, limiter
from models import EpisodeGuide, EpisodeTweetConfig, SocialConnection, Podcast
from services.tweet_scheduler import TweetSchedulerService
from utils.podcast_access import require_podcast_access, require_podcast_admin
from utils.logging import log_exception

from . import podcast_bp


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets')
@login_required
@require_podcast_access
def episode_tweets(podcast_id, episode_id):
    """View tweet configurations for an episode."""
    podcast = g.podcast
    episode = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    # Get all tweet configs for this episode
    tweet_configs = EpisodeTweetConfig.query.filter_by(
        episode_id=episode_id
    ).all()

    # Check if current user has a config
    user_config = next(
        (c for c in tweet_configs if c.user_id == current_user.id),
        None
    )

    # Check if current user has Twitter connected
    user_twitter = SocialConnection.query.filter_by(
        user_id=current_user.id,
        platform='twitter',
        is_active=True
    ).first()

    return render_template(
        'podcasts/tweets/episode_tweets.html',
        podcast=podcast,
        episode=episode,
        tweet_configs=tweet_configs,
        user_config=user_config,
        user_twitter=user_twitter,
    )


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets/my', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def my_tweet_config(podcast_id, episode_id):
    """View and edit current user's tweet config for an episode."""
    podcast = g.podcast
    episode = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    # Get or create user's tweet config
    config = EpisodeTweetConfig.query.filter_by(
        episode_id=episode_id,
        user_id=current_user.id
    ).first()

    if not config:
        config = EpisodeTweetConfig(
            episode_id=episode_id,
            user_id=current_user.id,
            enabled=True,
            include_url=True,
            status=EpisodeTweetConfig.STATUS_PENDING,
        )
        db.session.add(config)
        db.session.commit()

    # Check if user has Twitter connected
    user_twitter = SocialConnection.query.filter_by(
        user_id=current_user.id,
        platform='twitter',
        is_active=True
    ).first()

    if request.method == 'POST':
        try:
            # Update config from form
            config.enabled = request.form.get('enabled') == 'on'
            config.include_url = request.form.get('include_url') == 'on'

            custom_content = request.form.get('custom_content', '').strip()
            if custom_content:
                # Validate length
                if len(custom_content) > 280:
                    flash('Tweet content must be 280 characters or less.', 'error')
                    return redirect(url_for('podcasts.my_tweet_config',
                                          podcast_id=podcast_id, episode_id=episode_id))
                config.custom_content = custom_content
            else:
                config.custom_content = None

            db.session.commit()
            flash('Tweet settings saved.', 'success')
            return redirect(url_for('podcasts.episode_tweets',
                                  podcast_id=podcast_id, episode_id=episode_id))

        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(e, 'Failed to save tweet config')
            flash('Failed to save settings. Please try again.', 'error')

    return render_template(
        'podcasts/tweets/my_config.html',
        podcast=podcast,
        episode=episode,
        config=config,
        user_twitter=user_twitter,
    )


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets/generate', methods=['POST'])
@login_required
@require_podcast_access
@limiter.limit("5 per minute")
def generate_tweet(podcast_id, episode_id):
    """Generate AI-powered tweet content for the current user."""
    episode = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    # Get or create user's tweet config
    config = EpisodeTweetConfig.query.filter_by(
        episode_id=episode_id,
        user_id=current_user.id
    ).first()

    if not config:
        config = EpisodeTweetConfig(
            episode_id=episode_id,
            user_id=current_user.id,
            enabled=True,
            include_url=True,
            status=EpisodeTweetConfig.STATUS_PENDING,
        )
        db.session.add(config)

    try:
        scheduler_service = TweetSchedulerService()
        content = scheduler_service.generate_tweet_content(config, episode)

        if content:
            config.generated_content = content
            db.session.commit()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'content': content,
                    'character_count': len(content),
                })

            flash('Tweet content generated successfully.', 'success')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate content. Try adding more episode details.',
                })

            flash('Could not generate tweet content. Try adding more episode details.', 'warning')

    except Exception as e:
        log_exception(e, 'Failed to generate tweet content')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': 'An error occurred while generating content.',
            })
        flash('An error occurred while generating content.', 'error')

    return redirect(url_for('podcasts.my_tweet_config',
                          podcast_id=podcast_id, episode_id=episode_id))


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets/post-now', methods=['POST'])
@login_required
@require_podcast_access
@limiter.limit("5 per minute")
def post_tweet_now(podcast_id, episode_id):
    """Manually post a tweet for the current user (for testing).

    Delegates to TweetSchedulerService.post_tweet_for_user() for consistent behavior
    with automated posting. Only handles HTTP response formatting here.
    """
    # Verify episode belongs to podcast
    EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        scheduler_service = TweetSchedulerService()
        result = scheduler_service.post_tweet_for_user(current_user.id, episode_id)

        if result.get('success'):
            if is_ajax:
                return jsonify({
                    'success': True,
                    'tweet_url': result.get('tweet_url'),
                    'message': 'Tweet posted successfully!'
                })
            flash('Tweet posted successfully!', 'success')
        else:
            error_msg = result.get('error', 'Failed to post tweet.')
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg})
            flash(error_msg, 'error')

    except Exception as e:
        log_exception(e, 'Failed to post tweet manually')

        if is_ajax:
            return jsonify({'success': False, 'error': 'An error occurred while posting.'})
        flash('An error occurred while posting the tweet.', 'error')

    return redirect(url_for('podcasts.my_tweet_config',
                          podcast_id=podcast_id, episode_id=episode_id))


@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets/create-all', methods=['POST'])
@login_required
@require_podcast_admin
@limiter.limit("2 per minute")
def create_all_tweet_configs(podcast_id, episode_id):
    """Create tweet configs for all podcast members (admin only)."""
    podcast = g.podcast
    episode = EpisodeGuide.query.filter_by(
        id=episode_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        scheduler_service = TweetSchedulerService()
        configs = scheduler_service.create_tweet_configs_for_episode(
            episode,
            generate_content=True
        )

        flash(f'Created tweet configurations for {len(configs)} podcast members.', 'success')

    except Exception as e:
        log_exception(e, 'Failed to create tweet configs')
        flash('Failed to create tweet configurations.', 'error')

    return redirect(url_for('podcasts.episode_tweets',
                          podcast_id=podcast_id, episode_id=episode_id))


@podcast_bp.route('/<int:podcast_id>/settings/youtube', methods=['GET', 'POST'])
@login_required
@require_podcast_admin
def youtube_settings(podcast_id):
    """Configure YouTube channel for live detection.

    Supports both form-based and JSON API access:
    - Form: Standard HTML form submission
    - JSON: POST with Content-Type: application/json, GET with Accept: application/json
    """
    podcast = g.podcast
    is_json_request = request.is_json or request.headers.get('Accept') == 'application/json'

    if request.method == 'POST':
        try:
            # Accept JSON or form data
            if request.is_json:
                data = request.get_json()
                channel_id = (data.get('youtube_channel_id') or '').strip()
                title_filter_enabled = bool(data.get('youtube_title_filter_enabled', False))
                title_filter = (data.get('youtube_title_filter') or '').strip()
            else:
                channel_id = request.form.get('youtube_channel_id', '').strip()
                title_filter_enabled = request.form.get('youtube_title_filter_enabled') == 'on'
                title_filter = request.form.get('youtube_title_filter', '').strip()

            # Basic validation - YouTube channel IDs start with UC and are 24 chars
            channel_warning = None
            if channel_id and not (channel_id.startswith('UC') and len(channel_id) == 24):
                channel_warning = ('Standard YouTube channel IDs start with "UC" and are 24 characters. '
                                   'Make sure you\'ve entered the correct channel ID.')
                if not is_json_request:
                    flash(f'Note: {channel_warning}', 'warning')

            # Validate title filter length
            if title_filter and len(title_filter) > 200:
                error_msg = 'Title filter must be 200 characters or less.'
                if is_json_request:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('podcasts.youtube_settings', podcast_id=podcast_id))

            podcast.youtube_channel_id = channel_id if channel_id else None
            podcast.youtube_title_filter_enabled = title_filter_enabled
            podcast.youtube_title_filter = title_filter if title_filter else None

            db.session.commit()

            # Return JSON for API clients
            if is_json_request:
                response_data = {
                    'success': True,
                    'youtube_channel_id': podcast.youtube_channel_id,
                    'youtube_title_filter': podcast.youtube_title_filter,
                    'youtube_title_filter_enabled': podcast.youtube_title_filter_enabled,
                }
                if channel_warning:
                    response_data['warning'] = channel_warning
                return jsonify(response_data)

            if channel_id:
                flash('YouTube settings saved.', 'success')
            else:
                flash('YouTube channel ID cleared.', 'info')

            return redirect(url_for('podcasts.youtube_settings', podcast_id=podcast_id))

        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(e, 'Failed to save YouTube settings')
            if is_json_request:
                return jsonify({'success': False, 'error': 'Failed to save settings.'}), 500
            flash('Failed to save settings.', 'error')

    # GET: Return JSON if requested
    if is_json_request:
        return jsonify({
            'youtube_channel_id': podcast.youtube_channel_id,
            'youtube_title_filter': podcast.youtube_title_filter,
            'youtube_title_filter_enabled': podcast.youtube_title_filter_enabled,
        })

    return render_template(
        'podcasts/settings/youtube.html',
        podcast=podcast,
    )


@podcast_bp.route('/<int:podcast_id>/settings/youtube/test', methods=['POST'])
@login_required
@require_podcast_access
@limiter.limit("10 per minute")
def test_youtube_live(podcast_id):
    """Test YouTube live detection for a podcast."""
    podcast = g.podcast

    if not podcast.youtube_channel_id:
        return jsonify({
            'success': False,
            'error': 'No YouTube channel ID configured.',
        })

    try:
        from services.youtube_live import YouTubeLiveService
        youtube_service = YouTubeLiveService()
        result = youtube_service.check_channel_live(podcast.youtube_channel_id)

        return jsonify({
            'success': True,
            'is_live': result.get('is_live', False),
            'video_url': result.get('video_url'),
            'video_title': result.get('video_title'),
            'error': result.get('error'),
        })

    except Exception as e:
        log_exception(e, 'Failed to test YouTube live detection')
        return jsonify({
            'success': False,
            'error': 'An error occurred while testing YouTube live detection. Please check the channel ID and try again.',
        })
