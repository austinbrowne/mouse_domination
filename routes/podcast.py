from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import PodcastEpisode, Contact
from app import db
from datetime import datetime

podcast_bp = Blueprint('podcast', __name__)


@podcast_bp.route('/')
def list_episodes():
    """List all podcast episodes."""
    sponsored = request.args.get('sponsored')
    search = request.args.get('search', '')

    query = PodcastEpisode.query

    if sponsored == 'yes':
        query = query.filter_by(sponsored=True)
    elif sponsored == 'no':
        query = query.filter_by(sponsored=False)
    if search:
        query = query.filter(PodcastEpisode.title.ilike(f'%{search}%'))

    episodes = query.order_by(PodcastEpisode.publish_date.desc()).all()

    # Stats
    total_episodes = len(episodes)
    sponsored_count = sum(1 for e in episodes if e.sponsored)
    total_sponsor_revenue = sum(e.sponsor_amount or 0 for e in episodes if e.sponsored)

    return render_template('podcast/list.html',
        episodes=episodes,
        current_sponsored=sponsored,
        search=search,
        total_episodes=total_episodes,
        sponsored_count=sponsored_count,
        total_sponsor_revenue=total_sponsor_revenue,
    )


@podcast_bp.route('/new', methods=['GET', 'POST'])
def new_episode():
    """Create a new podcast episode."""
    if request.method == 'POST':
        episode = PodcastEpisode(
            episode_number=int(request.form['episode_number']) if request.form.get('episode_number') else None,
            title=request.form['title'],
            youtube_url=request.form.get('youtube_url') or None,
            topics=request.form.get('topics') or None,
            sponsored=request.form.get('sponsored') == 'yes',
            sponsor_name=request.form.get('sponsor_name') or None,
            sponsor_amount=float(request.form['sponsor_amount']) if request.form.get('sponsor_amount') else None,
            notes=request.form.get('notes') or None,
        )

        if request.form.get('publish_date'):
            episode.publish_date = datetime.strptime(request.form['publish_date'], '%Y-%m-%d').date()

        # Link guests
        guest_ids = request.form.getlist('guest_ids')
        if guest_ids:
            guests = Contact.query.filter(Contact.id.in_(guest_ids)).all()
            episode.guests = guests

        db.session.add(episode)
        db.session.commit()
        flash(f'Episode "{episode.title}" created successfully.', 'success')
        return redirect(url_for('podcast.list_episodes'))

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
        episode.episode_number = int(request.form['episode_number']) if request.form.get('episode_number') else None
        episode.title = request.form['title']
        episode.youtube_url = request.form.get('youtube_url') or None
        episode.topics = request.form.get('topics') or None
        episode.sponsored = request.form.get('sponsored') == 'yes'
        episode.sponsor_name = request.form.get('sponsor_name') or None
        episode.sponsor_amount = float(request.form['sponsor_amount']) if request.form.get('sponsor_amount') else None
        episode.notes = request.form.get('notes') or None
        episode.publish_date = datetime.strptime(request.form['publish_date'], '%Y-%m-%d').date() if request.form.get('publish_date') else None

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
