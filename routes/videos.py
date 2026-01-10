from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import Video, Company, Inventory
from app import db
from services.youtube import YouTubeService
from datetime import datetime

videos_bp = Blueprint('videos', __name__)


@videos_bp.route('/')
def list_videos():
    """List all videos with optional filtering."""
    video_type = request.args.get('type')
    sponsored = request.args.get('sponsored')
    search = request.args.get('search', '')
    show = request.args.get('show', 'all')  # all, videos, shorts, podcasts

    query = Video.query

    if video_type:
        query = query.filter_by(video_type=video_type)
    if sponsored == 'yes':
        query = query.filter_by(sponsored=True)
    elif sponsored == 'no':
        query = query.filter_by(sponsored=False)
    if search:
        query = query.filter(Video.title.ilike(f'%{search}%'))
    if show == 'shorts':
        query = query.filter_by(is_short=True)
    elif show == 'podcasts':
        query = query.filter_by(is_podcast=True)
    elif show == 'videos':
        query = query.filter_by(is_short=False, is_podcast=False)

    videos = query.order_by(Video.publish_date.desc()).all()

    # Stats
    total_views = sum(v.views or 0 for v in videos)
    sponsored_count = sum(1 for v in videos if v.sponsored)
    total_sponsor_revenue = sum(v.sponsor_amount or 0 for v in videos if v.sponsored)

    # Check if YouTube is configured
    yt_service = YouTubeService()
    youtube_configured = yt_service.is_configured

    return render_template('videos/list.html',
        videos=videos,
        current_type=video_type,
        current_sponsored=sponsored,
        current_show=show,
        search=search,
        total_views=total_views,
        sponsored_count=sponsored_count,
        total_sponsor_revenue=total_sponsor_revenue,
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
    return redirect(url_for('videos.list_videos'))


@videos_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_video(id):
    """Edit business metadata for a video."""
    video = Video.query.get_or_404(id)

    if request.method == 'POST':
        # For non-synced videos, allow editing title/url/etc
        if not video.youtube_id:
            video.title = request.form['title']
            video.url = request.form.get('url') or None
            video.views = int(request.form['views']) if request.form.get('views') else None
            if request.form.get('publish_date'):
                video.publish_date = datetime.strptime(request.form['publish_date'], '%Y-%m-%d').date()
            video.is_short = request.form.get('is_short') == 'yes'

        video.video_type = request.form.get('video_type', 'review')
        video.company_id = request.form.get('company_id') or None
        video.sponsored = request.form.get('sponsored') == 'yes'
        video.sponsor_amount = float(request.form['sponsor_amount']) if request.form.get('sponsor_amount') else None
        video.affiliate_links = request.form.get('affiliate_links') == 'yes'
        video.notes = request.form.get('notes') or None
        video.is_podcast = request.form.get('is_podcast') == 'yes'

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

    companies = Company.query.order_by(Company.name).all()
    products = Inventory.query.order_by(Inventory.product_name).all()
    return render_template('videos/form.html', video=video, companies=companies, products=products)


@videos_bp.route('/<int:id>/delete', methods=['POST'])
def delete_video(id):
    """Delete a video."""
    video = Video.query.get_or_404(id)
    title = video.title
    db.session.delete(video)
    db.session.commit()
    flash(f'Video "{title}" deleted.', 'success')
    return redirect(url_for('videos.list_videos'))


# Keep manual entry as fallback for users without API
@videos_bp.route('/new', methods=['GET', 'POST'])
def new_video():
    """Manually create a video (fallback when API not configured)."""
    if request.method == 'POST':
        video = Video(
            title=request.form['title'],
            url=request.form.get('url') or None,
            video_type=request.form.get('video_type', 'review'),
            company_id=request.form.get('company_id') or None,
            sponsored=request.form.get('sponsored') == 'yes',
            sponsor_amount=float(request.form['sponsor_amount']) if request.form.get('sponsor_amount') else None,
            affiliate_links=request.form.get('affiliate_links') == 'yes',
            views=int(request.form['views']) if request.form.get('views') else None,
            notes=request.form.get('notes') or None,
            is_podcast=request.form.get('is_podcast') == 'yes',
            is_short=request.form.get('is_short') == 'yes',
        )

        if request.form.get('publish_date'):
            video.publish_date = datetime.strptime(request.form['publish_date'], '%Y-%m-%d').date()

        # Link products
        product_ids = request.form.getlist('product_ids')
        if product_ids:
            products = Inventory.query.filter(Inventory.id.in_(product_ids)).all()
            video.products = products

        db.session.add(video)
        db.session.commit()
        flash(f'Video "{video.title}" created.', 'success')
        return redirect(url_for('videos.list_videos'))

    companies = Company.query.order_by(Company.name).all()
    products = Inventory.query.order_by(Inventory.product_name).all()
    return render_template('videos/form.html', video=None, companies=companies, products=products)
