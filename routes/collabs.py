from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Collaboration, Contact
from app import db
from constants import (
    COLLAB_TYPE_CHOICES, COLLAB_STATUS_CHOICES, PLATFORM_CHOICES, DEFAULT_PAGE_SIZE
)
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.queries import get_contacts_for_dropdown

collabs_bp = Blueprint('collabs', __name__)


@collabs_bp.route('/')
def list_collabs():
    """List all collaborations with optional filtering and pagination."""
    collab_type = request.args.get('type')
    status = request.args.get('status')
    follow_up = request.args.get('follow_up')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # Eager load contact to avoid N+1
    query = Collaboration.query.options(joinedload(Collaboration.contact))

    if collab_type and collab_type in COLLAB_TYPE_CHOICES:
        query = query.filter_by(collab_type=collab_type)
    if status and status in COLLAB_STATUS_CHOICES:
        query = query.filter_by(status=status)
    if follow_up == 'yes':
        query = query.filter_by(follow_up_needed=True)
    if search:
        # Search by contact name
        query = query.join(Contact).filter(Contact.name.ilike(f"%{search}%"))

    # Paginated query
    pagination = query.order_by(Collaboration.created_at.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Stats - single aggregated query for all status counts
    stats_result = db.session.query(
        func.sum(case((Collaboration.status == 'idea', 1), else_=0)).label('idea'),
        func.sum(case((Collaboration.status == 'reached_out', 1), else_=0)).label('reached_out'),
        func.sum(case((Collaboration.status == 'confirmed', 1), else_=0)).label('confirmed'),
        func.sum(case((Collaboration.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(case((Collaboration.follow_up_needed == True, 1), else_=0)).label('need_follow_up')
    ).first()

    # Create stats dict for template
    stats = {
        'idea': int(stats_result.idea or 0),
        'reached_out': int(stats_result.reached_out or 0),
        'confirmed': int(stats_result.confirmed or 0),
        'completed': int(stats_result.completed or 0),
    }

    contacts = get_contacts_for_dropdown()

    return render_template('collabs/list.html',
        collabs=pagination.items,
        pagination=pagination,
        contacts=contacts,
        current_type=collab_type,
        current_status=status,
        current_follow_up=follow_up,
        search=search,
        stats=stats,
        need_follow_up=int(stats_result.need_follow_up or 0),
    )


@collabs_bp.route('/new', methods=['GET', 'POST'])
def new_collab():
    """Create a new collaboration."""
    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Validate required contact
            contact_id = form.foreign_key('contact_id', Contact)
            if not contact_id:
                raise ValidationError('Contact', 'This field is required.')

            # Handle platform choice with fallback
            platform = form.choice('their_platform', PLATFORM_CHOICES)
            if form.optional('their_platform') and not platform:
                platform = 'other'

            collab = Collaboration(
                contact_id=contact_id,
                collab_type=form.choice('collab_type', COLLAB_TYPE_CHOICES, default='collab_video'),
                status=form.choice('status', COLLAB_STATUS_CHOICES, default='idea'),
                scheduled_date=form.date('scheduled_date'),
                completed_date=form.date('completed_date'),
                their_channel=form.optional('their_channel'),
                their_platform=platform,
                audience_size=form.integer('audience_size'),
                result_views=form.integer('result_views'),
                result_new_subs=form.integer('result_new_subs'),
                result_notes=form.optional('result_notes'),
                follow_up_needed=form.boolean('follow_up_needed'),
                follow_up_date=form.date('follow_up_date'),
                notes=form.optional('notes'),
            )

            db.session.add(collab)
            db.session.commit()
            flash('Collaboration created successfully.', 'success')
            return redirect(url_for('collabs.list_collabs'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            contacts = get_contacts_for_dropdown()
            return render_template('collabs/form.html', collab=None, contacts=contacts)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            contacts = get_contacts_for_dropdown()
            return render_template('collabs/form.html', collab=None, contacts=contacts)

    contacts = get_contacts_for_dropdown()
    return render_template('collabs/form.html', collab=None, contacts=contacts)


@collabs_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_collab(id):
    """Edit an existing collaboration."""
    collab = Collaboration.query.options(joinedload(Collaboration.contact)).get_or_404(id)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Validate required contact
            contact_id = form.foreign_key('contact_id', Contact)
            if not contact_id:
                raise ValidationError('Contact', 'This field is required.')

            # Handle platform choice with fallback
            platform = form.choice('their_platform', PLATFORM_CHOICES)
            if form.optional('their_platform') and not platform:
                platform = 'other'

            collab.contact_id = contact_id
            collab.collab_type = form.choice('collab_type', COLLAB_TYPE_CHOICES, default='collab_video')
            collab.status = form.choice('status', COLLAB_STATUS_CHOICES, default='idea')
            collab.scheduled_date = form.date('scheduled_date')
            collab.completed_date = form.date('completed_date')
            collab.their_channel = form.optional('their_channel')
            collab.their_platform = platform
            collab.audience_size = form.integer('audience_size')
            collab.result_views = form.integer('result_views')
            collab.result_new_subs = form.integer('result_new_subs')
            collab.result_notes = form.optional('result_notes')
            collab.follow_up_needed = form.boolean('follow_up_needed')
            collab.follow_up_date = form.date('follow_up_date')
            collab.notes = form.optional('notes')

            db.session.commit()
            flash('Collaboration updated successfully.', 'success')
            return redirect(url_for('collabs.list_collabs'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            contacts = get_contacts_for_dropdown()
            return render_template('collabs/form.html', collab=collab, contacts=contacts)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            contacts = get_contacts_for_dropdown()
            return render_template('collabs/form.html', collab=collab, contacts=contacts)

    contacts = get_contacts_for_dropdown()
    return render_template('collabs/form.html', collab=collab, contacts=contacts)


@collabs_bp.route('/<int:id>/delete', methods=['POST'])
def delete_collab(id):
    """Delete a collaboration."""
    try:
        collab = Collaboration.query.get_or_404(id)
        db.session.delete(collab)
        db.session.commit()
        flash('Collaboration deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('collabs.list_collabs'))


@collabs_bp.route('/<int:id>/complete', methods=['POST'])
def complete_collab(id):
    """Quick action to mark a collaboration as completed."""
    try:
        collab = Collaboration.query.get_or_404(id)
        collab.status = 'completed'
        collab.completed_date = db.func.current_date()
        db.session.commit()
        flash('Collaboration marked as completed.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('collabs.list_collabs'))


@collabs_bp.route('/<int:id>/clear-followup', methods=['POST'])
def clear_followup(id):
    """Clear follow-up flag."""
    try:
        collab = Collaboration.query.get_or_404(id)
        collab.follow_up_needed = False
        collab.follow_up_date = None
        db.session.commit()
        flash('Follow-up cleared.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('collabs.list_collabs'))
