from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import PodcastEpisode, Contact
from app import db
from utils.validation import (
    parse_date, parse_float, parse_int, validate_required,
    or_none, ValidationError
)

podcast_bp = Blueprint('podcast', __name__)


@podcast_bp.route('/')
def list_episodes():
    """List all podcast episodes."""
    sponsored = request.args.get('sponsored')
    search = request.args.get('search', '').strip()

    query = PodcastEpisode.query.options(joinedload(PodcastEpisode.guests))

    if sponsored == 'yes':
        query = query.filter_by(sponsored=True)
    elif sponsored == 'no':
        query = query.filter_by(sponsored=False)
    if search:
        query = query.filter(PodcastEpisode.title.ilike('%' + search + '%'))

    episodes = query.order_by(PodcastEpisode.publish_date.desc()).all()

    # Stats using database aggregation
    stats = db.session.query(
        func.count(PodcastEpisode.id).label('total'),
        func.sum(func.cast(PodcastEpisode.sponsored == True, db.Integer)).label('sponsored_count'),
        func.coalesce(func.sum(func.cast(PodcastEpisode.sponsored == True, db.Integer) * func.coalesce(PodcastEpisode.sponsor_amount, 0)), 0).label('sponsor_revenue')
    ).first()

    return render_template('podcast/list.html',
        episodes=episodes,
        current_sponsored=sponsored,
        search=search,
        total_episodes=stats.total or 0,
        sponsored_count=stats.sponsored_count or 0,
        total_sponsor_revenue=stats.sponsor_revenue or 0,
    )


@podcast_bp.route('/new', methods=['GET', 'POST'])
def new_episode():
    """Create a new podcast episode."""
    if request.method == 'POST':
        try:
            title = validate_required(request.form.get('title', ''), 'Title')
            episode_number = parse_int(request.form.get('episode_number', ''), 'Episode Number', allow_negative=False)
            publish_date = parse_date(request.form.get('publish_date', ''), 'Publish Date')
            sponsor_amount = parse_float(request.form.get('sponsor_amount', ''), 'Sponsor Amount', allow_negative=False)

            episode = PodcastEpisode(
                episode_number=episode_number,
                title=title,
                youtube_url=or_none(request.form.get('youtube_url', '')),
                topics=or_none(request.form.get('topics', '')),
                sponsored=request.form.get('sponsored') == 'yes',
                sponsor_name=or_none(request.form.get('sponsor_name', '')),
                sponsor_amount=sponsor_amount,
                notes=or_none(request.form.get('notes', '')),
                publish_date=publish_date,
            )

            # Link guests
            guest_ids = request.form.getlist('guest_ids')
            if guest_ids:
                guests = Contact.query.filter(Contact.id.in_(guest_ids)).all()
                episode.guests = guests

            db.session.add(episode)
            db.session.commit()
            flash(f'Episode "{episode.title}" created successfully.', 'success')
            return redirect(url_for('podcast.list_episodes'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            contacts = Contact.query.order_by(Contact.name).all()
            last_episode = PodcastEpisode.query.order_by(PodcastEpisode.episode_number.desc()).first()
            next_number = (last_episode.episode_number or 0) + 1 if last_episode else 1
            return render_template('podcast/form.html', episode=None, contacts=contacts, next_number=next_number)

    contacts = Contact.query.order_by(Contact.name).all()
    # Get next episode number
    last_episode = PodcastEpisode.query.order_by(PodcastEpisode.episode_number.desc()).first()
    next_number = (last_episode.episode_number or 0) + 1 if last_episode else 1

    return render_template('podcast/form.html', episode=None, contacts=contacts, next_number=next_number)


@podcast_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_episode(id):
    """Edit an existing podcast episode."""
    episode = PodcastEpisode.query.get_or_404(id)

    if request.method == 'POST':
        try:
            title = validate_required(request.form.get('title', ''), 'Title')
            episode_number = parse_int(request.form.get('episode_number', ''), 'Episode Number', allow_negative=False)
            publish_date = parse_date(request.form.get('publish_date', ''), 'Publish Date')
            sponsor_amount = parse_float(request.form.get('sponsor_amount', ''), 'Sponsor Amount', allow_negative=False)

            episode.episode_number = episode_number
            episode.title = title
            episode.youtube_url = or_none(request.form.get('youtube_url', ''))
            episode.topics = or_none(request.form.get('topics', ''))
            episode.sponsored = request.form.get('sponsored') == 'yes'
            episode.sponsor_name = or_none(request.form.get('sponsor_name', ''))
            episode.sponsor_amount = sponsor_amount
            episode.notes = or_none(request.form.get('notes', ''))
            episode.publish_date = publish_date

            # Update guests
            guest_ids = request.form.getlist('guest_ids')
            if guest_ids:
                guests = Contact.query.filter(Contact.id.in_(guest_ids)).all()
                episode.guests = guests
            else:
                episode.guests = []

            db.session.commit()
            flash(f'Episode "{episode.title}" updated successfully.', 'success')
            return redirect(url_for('podcast.list_episodes'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('podcast/form.html', episode=episode, contacts=contacts, next_number=None)

    contacts = Contact.query.order_by(Contact.name).all()
    return render_template('podcast/form.html', episode=episode, contacts=contacts, next_number=None)


@podcast_bp.route('/<int:id>/delete', methods=['POST'])
def delete_episode(id):
    """Delete a podcast episode."""
    episode = PodcastEpisode.query.get_or_404(id)
    title = episode.title
    db.session.delete(episode)
    db.session.commit()
    flash(f'Episode "{title}" deleted.', 'success')
    return redirect(url_for('podcast.list_episodes'))
