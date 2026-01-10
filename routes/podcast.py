from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import PodcastEpisode, Contact
from app import db
from constants import DEFAULT_PAGE_SIZE
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.queries import get_contacts_for_dropdown

podcast_bp = Blueprint('podcast', __name__)


@podcast_bp.route('/')
def list_episodes():
    """List all podcast episodes with pagination."""
    sponsored = request.args.get('sponsored')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # Eager load guests to avoid N+1
    query = PodcastEpisode.query.options(joinedload(PodcastEpisode.guests))

    if sponsored == 'yes':
        query = query.filter_by(sponsored=True)
    elif sponsored == 'no':
        query = query.filter_by(sponsored=False)
    if search:
        query = query.filter(PodcastEpisode.title.ilike(f"%{search}%"))

    # Paginated query
    pagination = query.order_by(PodcastEpisode.publish_date.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Stats using database aggregation
    stats = db.session.query(
        func.count(PodcastEpisode.id).label('total'),
        func.sum(func.cast(PodcastEpisode.sponsored == True, db.Integer)).label('sponsored_count'),
        func.coalesce(func.sum(func.cast(PodcastEpisode.sponsored == True, db.Integer) * func.coalesce(PodcastEpisode.sponsor_amount, 0)), 0).label('sponsor_revenue')
    ).first()

    return render_template('podcast/list.html',
        episodes=pagination.items,
        pagination=pagination,
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
            form = FormData(request.form)

            episode = PodcastEpisode(
                episode_number=form.integer('episode_number', allow_negative=False),
                title=form.required('title'),
                youtube_url=form.optional('youtube_url'),
                topics=form.optional('topics'),
                sponsored=form.boolean('sponsored'),
                sponsor_name=form.optional('sponsor_name'),
                sponsor_amount=form.decimal('sponsor_amount', allow_negative=False),
                notes=form.optional('notes'),
                publish_date=form.date('publish_date'),
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
            contacts = get_contacts_for_dropdown()
            last_episode = PodcastEpisode.query.order_by(PodcastEpisode.episode_number.desc()).first()
            next_number = (last_episode.episode_number or 0) + 1 if last_episode else 1
            return render_template('podcast/form.html', episode=None, contacts=contacts, next_number=next_number)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            contacts = get_contacts_for_dropdown()
            last_episode = PodcastEpisode.query.order_by(PodcastEpisode.episode_number.desc()).first()
            next_number = (last_episode.episode_number or 0) + 1 if last_episode else 1
            return render_template('podcast/form.html', episode=None, contacts=contacts, next_number=next_number)

    contacts = get_contacts_for_dropdown()
    # Get next episode number
    last_episode = PodcastEpisode.query.order_by(PodcastEpisode.episode_number.desc()).first()
    next_number = (last_episode.episode_number or 0) + 1 if last_episode else 1

    return render_template('podcast/form.html', episode=None, contacts=contacts, next_number=next_number)


@podcast_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_episode(id):
    """Edit an existing podcast episode."""
    episode = PodcastEpisode.query.options(joinedload(PodcastEpisode.guests)).get_or_404(id)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            episode.episode_number = form.integer('episode_number', allow_negative=False)
            episode.title = form.required('title')
            episode.youtube_url = form.optional('youtube_url')
            episode.topics = form.optional('topics')
            episode.sponsored = form.boolean('sponsored')
            episode.sponsor_name = form.optional('sponsor_name')
            episode.sponsor_amount = form.decimal('sponsor_amount', allow_negative=False)
            episode.notes = form.optional('notes')
            episode.publish_date = form.date('publish_date')

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
            contacts = get_contacts_for_dropdown()
            return render_template('podcast/form.html', episode=episode, contacts=contacts, next_number=None)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            contacts = get_contacts_for_dropdown()
            return render_template('podcast/form.html', episode=episode, contacts=contacts, next_number=None)

    contacts = get_contacts_for_dropdown()
    return render_template('podcast/form.html', episode=episode, contacts=contacts, next_number=None)


@podcast_bp.route('/<int:id>/delete', methods=['POST'])
def delete_episode(id):
    """Delete a podcast episode."""
    try:
        episode = PodcastEpisode.query.get_or_404(id)
        title = episode.title
        db.session.delete(episode)
        db.session.commit()
        flash(f'Episode "{title}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('podcast.list_episodes'))
