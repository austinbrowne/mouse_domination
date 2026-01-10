from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Video, Company, Inventory
from app import db
from services.youtube import YouTubeService
from datetime import datetime
from constants import VIDEO_TYPE_CHOICES, DEFAULT_PAGE_SIZE
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.queries import get_companies_for_dropdown

videos_bp = Blueprint('videos', __name__)


@videos_bp.route('/')
def list_videos():
    """List all videos with optional filtering and pagination."""
    video_type = request.args.get('type')
    sponsored = request.args.get('sponsored')
    search = request.args.get('search', '').strip()
    show = request.args.get('show', 'all')  # all, videos, shorts, podcasts
    page = request.args.get('page', 1, type=int)

    query = Video.query.options(joinedload(Video.company))

    if video_type and video_type in VIDEO_TYPE_CHOICES:
        query = query.filter_by(video_type=video_type)
    if sponsored == 'yes':
        query = query.filter_by(sponsored=True)
    elif sponsored == 'no':
        query = query.filter_by(sponsored=False)
    if search:
        query = query.filter(Video.title.ilike(f"%{search}%"))
    if show == 'shorts':
        query = query.filter_by(is_short=True)
    elif show == 'podcasts':
        query = query.filter_by(is_podcast=True)
    elif show == 'videos':
        query = query.filter_by(is_short=False, is_podcast=False)

    # Paginated query
    pagination = query.order_by(Video.publish_date.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Stats using database aggregation for efficiency
    stats = db.session.query(
        func.coalesce(func.sum(Video.views), 0).label('total_views'),
        func.sum(func.cast(Video.sponsored == True, db.Integer)).label('sponsored_count'),
        func.coalesce(func.sum(func.cast(Video.sponsored == True, db.Integer) * func.coalesce(Video.sponsor_amount, 0)), 0).label('sponsor_revenue')
    ).first()

    # Check if YouTube is configured
    yt_service = YouTubeService()
    youtube_configured = yt_service.is_configured

    return render_template('videos/list.html',
        videos=pagination.items,
        pagination=pagination,
        current_type=video_type,
        current_sponsored=sponsored,
        current_show=show,
        search=search,
        total_views=stats.total_views or 0,
        sponsored_count=stats.sponsored_count or 0,
        total_sponsor_revenue=stats.sponsor_revenue or 0,
        youtube_configured=youtube_configured,
    )


@videos_bp.route('/sync', methods=['POST'])
def sync_videos():
    """Sync videos from YouTube channel."""
    yt_service = YouTubeService()

    if not yt_service.is_configured:
        flash('YouTube API not configured. Set YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID environment variables.', 'error')
        return redirect(url_for('videos.list_videos'))

    # Fetch videos from YouTube
    result = yt_service.get_channel_videos(max_results=50)

    if 'error' in result:
        flash(f'YouTube API error: {result["error"]}', 'error')
        return redirect(url_for('videos.list_videos'))

    try:
        new_count = 0
        updated_count = 0

        for video_data in result['videos']:
            # Check if video already exists
            existing = Video.query.filter_by(youtube_id=video_data['youtube_id']).first()

            if existing:
                # Update stats
                existing.views = video_data['views']
                existing.likes = video_data['likes']
                existing.comments = video_data['comments']
                existing.last_synced = datetime.now()
                updated_count += 1
            else:
                # Create new video
                video = Video(
                    youtube_id=video_data['youtube_id'],
                    title=video_data['title'],
                    description=video_data['description'],
                    url=video_data['url'],
                    thumbnail_url=video_data['thumbnail_url'],
                    publish_date=video_data['publish_date'],
                    duration=video_data['duration'],
                    views=video_data['views'],
                    likes=video_data['likes'],
                    comments=video_data['comments'],
                    is_short=video_data['is_short'],
                    last_synced=datetime.now(),
                )
                db.session.add(video)
                new_count += 1

        db.session.commit()
        flash(f'Synced {new_count} new videos, updated {updated_count} existing.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred during sync.', 'error')
    return redirect(url_for('videos.list_videos'))


@videos_bp.route('/refresh-stats', methods=['POST'])
def refresh_stats():
    """Refresh view counts for all synced videos."""
    yt_service = YouTubeService()

    if not yt_service.is_configured:
        flash('YouTube API not configured.', 'error')
        return redirect(url_for('videos.list_videos'))

    # Get all videos with YouTube IDs
    videos = Video.query.filter(Video.youtube_id.isnot(None)).all()

    if not videos:
        flash('No synced videos to refresh.', 'info')
        return redirect(url_for('videos.list_videos'))

    try:
        # Batch refresh (API allows up to 50 at once)
        youtube_ids = [v.youtube_id for v in videos]
        updated_data = yt_service.get_video_details(youtube_ids)

        # Create lookup by youtube_id
        data_lookup = {d['youtube_id']: d for d in updated_data}

        updated_count = 0
        for video in videos:
            if video.youtube_id in data_lookup:
                data = data_lookup[video.youtube_id]
                video.views = data['views']
                video.likes = data['likes']
                video.comments = data['comments']
                video.last_synced = datetime.now()
                updated_count += 1

        db.session.commit()
        flash(f'Refreshed stats for {updated_count} videos.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred during refresh.', 'error')
    return redirect(url_for('videos.list_videos'))


@videos_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_video(id):
    """Edit business metadata for a video."""
    video = Video.query.options(
        joinedload(Video.company),
        joinedload(Video.products)
    ).get_or_404(id)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # For non-synced videos, allow editing title/url/etc
            if not video.youtube_id:
                video.title = form.required('title')
                video.url = form.optional('url')
                video.views = form.integer('views', allow_negative=False)
                video.publish_date = form.date('publish_date')
                video.is_short = form.boolean('is_short')

            video.video_type = form.choice('video_type', VIDEO_TYPE_CHOICES, default='review')
            video.company_id = form.foreign_key('company_id', Company)
            video.sponsored = form.boolean('sponsored')
            video.sponsor_amount = form.decimal('sponsor_amount', allow_negative=False)
            video.affiliate_links = form.boolean('affiliate_links')
            video.notes = form.optional('notes')
            video.is_podcast = form.boolean('is_podcast')

            # Update linked products
            product_ids = request.form.getlist('product_ids')
            if product_ids:
                products = Inventory.query.filter(Inventory.id.in_(product_ids)).all()
                video.products = products
            else:
                video.products = []

            db.session.commit()
            flash(f'Video "{video.title}" updated.', 'success')
            return redirect(url_for('videos.list_videos'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            products = Inventory.query.order_by(Inventory.product_name).all()
            return render_template('videos/form.html', video=video, companies=companies, products=products)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            products = Inventory.query.order_by(Inventory.product_name).all()
            return render_template('videos/form.html', video=video, companies=companies, products=products)

    companies = get_companies_for_dropdown()
    products = Inventory.query.order_by(Inventory.product_name).all()
    return render_template('videos/form.html', video=video, companies=companies, products=products)


@videos_bp.route('/<int:id>/delete', methods=['POST'])
def delete_video(id):
    """Delete a video."""
    try:
        video = Video.query.get_or_404(id)
        title = video.title
        db.session.delete(video)
        db.session.commit()
        flash(f'Video "{title}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('videos.list_videos'))


# Keep manual entry as fallback for users without API
@videos_bp.route('/new', methods=['GET', 'POST'])
def new_video():
    """Manually create a video (fallback when API not configured)."""
    if request.method == 'POST':
        try:
            form = FormData(request.form)

            video = Video(
                title=form.required('title'),
                url=form.optional('url'),
                video_type=form.choice('video_type', VIDEO_TYPE_CHOICES, default='review'),
                company_id=form.foreign_key('company_id', Company),
                sponsored=form.boolean('sponsored'),
                sponsor_amount=form.decimal('sponsor_amount', allow_negative=False),
                affiliate_links=form.boolean('affiliate_links'),
                views=form.integer('views', allow_negative=False),
                notes=form.optional('notes'),
                is_podcast=form.boolean('is_podcast'),
                is_short=form.boolean('is_short'),
                publish_date=form.date('publish_date'),
            )

            # Link products
            product_ids = request.form.getlist('product_ids')
            if product_ids:
                products = Inventory.query.filter(Inventory.id.in_(product_ids)).all()
                video.products = products

            db.session.add(video)
            db.session.commit()
            flash(f'Video "{video.title}" created.', 'success')
            return redirect(url_for('videos.list_videos'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            products = Inventory.query.order_by(Inventory.product_name).all()
            return render_template('videos/form.html', video=None, companies=companies, products=products)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            products = Inventory.query.order_by(Inventory.product_name).all()
            return render_template('videos/form.html', video=None, companies=companies, products=products)

    companies = get_companies_for_dropdown()
    products = Inventory.query.order_by(Inventory.product_name).all()
    return render_template('videos/form.html', video=None, companies=companies, products=products)
