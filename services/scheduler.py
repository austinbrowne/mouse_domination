"""APScheduler setup for background jobs.

This module initializes APScheduler for running periodic tasks like:
- Checking YouTube channels for live streams
- Posting scheduled tweets

The scheduler uses SQLAlchemy job store for persistence across restarts.
"""

import os
import atexit
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

# Global scheduler instance
scheduler = None


def init_scheduler(app: Flask):
    """
    Initialize the APScheduler with the Flask app.

    Args:
        app: Flask application instance
    """
    global scheduler

    # Don't initialize in testing mode
    if app.config.get('TESTING'):
        return

    # Don't initialize if explicitly disabled
    if os.environ.get('DISABLE_SCHEDULER', '').lower() in ('true', '1', 'yes'):
        app.logger.info('Scheduler disabled via DISABLE_SCHEDULER env var')
        return

    # Prevent double initialization (important for Flask reloader)
    if scheduler is not None:
        return

    # Get database URL from app config
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI')

    if not db_url:
        app.logger.warning('No database URL configured, scheduler not started')
        return

    # Configure job stores and executors
    jobstores = {
        'default': SQLAlchemyJobStore(url=db_url, tablename='apscheduler_jobs')
    }

    executors = {
        'default': ThreadPoolExecutor(max_workers=2)
    }

    job_defaults = {
        'coalesce': True,  # Combine multiple missed runs into one
        'max_instances': 1,  # Only one instance of each job at a time
        'misfire_grace_time': 60,  # 60 seconds grace period for missed jobs
    }

    # Create scheduler
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone='UTC',
    )

    # Add jobs
    _add_jobs(app)

    # Start scheduler
    scheduler.start()
    app.logger.info('APScheduler started')

    # Shut down scheduler when app exits
    atexit.register(lambda: shutdown_scheduler(app))


def shutdown_scheduler(app: Flask = None):
    """Shut down the scheduler gracefully."""
    global scheduler

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        if app:
            app.logger.info('APScheduler shut down')
        scheduler = None


def _add_jobs(app: Flask):
    """
    Add scheduled jobs to the scheduler.

    Args:
        app: Flask application instance
    """
    # Check for live streams every 3 minutes
    # This balances responsiveness with not hammering YouTube
    check_interval_minutes = int(os.environ.get('LIVE_CHECK_INTERVAL_MINUTES', '3'))

    scheduler.add_job(
        func=_job_check_live_streams,
        trigger='interval',
        minutes=check_interval_minutes,
        id='check_live_streams',
        name='Check YouTube channels for live streams',
        replace_existing=True,
        kwargs={'app': app},
    )

    app.logger.info(f'Added job: check_live_streams (every {check_interval_minutes} minutes)')


def _job_check_live_streams(app: Flask):
    """
    Job: Check all podcasts for live streams and post tweets.

    This runs within the Flask application context.
    """
    with app.app_context():
        try:
            from services.tweet_scheduler import TweetSchedulerService

            service = TweetSchedulerService()
            results = service.check_and_post_live_tweets()

            # Log summary
            live_count = sum(1 for r in results if r.get('is_live'))
            tweets_posted = sum(r.get('tweets_posted', 0) for r in results)

            if live_count > 0 or tweets_posted > 0:
                app.logger.info(
                    f'Live check complete: {live_count} live streams, {tweets_posted} tweets posted'
                )

        except Exception as e:
            app.logger.error(f'Error in check_live_streams job: {e}')


def get_scheduler():
    """Get the scheduler instance."""
    return scheduler


def is_scheduler_running() -> bool:
    """Check if the scheduler is running."""
    return scheduler is not None and scheduler.running
