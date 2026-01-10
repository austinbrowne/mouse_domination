from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Collaboration, Contact
from app import db
from constants import (
    COLLAB_TYPE_CHOICES, COLLAB_STATUS_CHOICES, PLATFORM_CHOICES, DEFAULT_PAGE_SIZE
)
from utils.validation import (
    parse_date, parse_int, validate_required, validate_foreign_key,
    validate_choice, or_none, ValidationError
)

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

    # Stats
    total = Collaboration.query.count()
    active = Collaboration.query.filter(
        Collaboration.status.in_(['idea', 'reached_out', 'confirmed'])
    ).count()
    completed = Collaboration.query.filter_by(status='completed').count()
    need_follow_up = Collaboration.query.filter_by(follow_up_needed=True).count()

    contacts = Contact.query.order_by(Contact.name).all()

    return render_template('collabs/list.html',
        collabs=pagination.items,
        pagination=pagination,
        contacts=contacts,
        current_type=collab_type,
        current_status=status,
        current_follow_up=follow_up,
        search=search,
        total=total,
        active=active,
        completed=completed,
        need_follow_up=need_follow_up,
    )


@collabs_bp.route('/new', methods=['GET', 'POST'])
def new_collab():
    """Create a new collaboration."""
    if request.method == 'POST':
        try:
            # Validate contact
            contact_id = validate_foreign_key(Contact, request.form.get('contact_id'), 'Contact')
            if not contact_id:
                raise ValidationError('Contact', 'This field is required.')

            # Validate choices
            collab_type = request.form.get('collab_type', 'collab_video')
            if collab_type not in COLLAB_TYPE_CHOICES:
                collab_type = 'collab_video'

            status = request.form.get('status', 'idea')
            if status not in COLLAB_STATUS_CHOICES:
                status = 'idea'

            platform = or_none(request.form.get('their_platform', ''))
            if platform and platform not in PLATFORM_CHOICES:
                platform = 'other'

            # Parse dates
            scheduled_date = parse_date(request.form.get('scheduled_date', ''), 'Scheduled Date')
            completed_date = parse_date(request.form.get('completed_date', ''), 'Completed Date')
            follow_up_date = parse_date(request.form.get('follow_up_date', ''), 'Follow-up Date')

            # Parse numbers
            audience_size = parse_int(request.form.get('audience_size', ''), 'Audience Size')
            result_views = parse_int(request.form.get('result_views', ''), 'Result Views')
            result_new_subs = parse_int(request.form.get('result_new_subs', ''), 'New Subscribers')

            collab = Collaboration(
                contact_id=contact_id,
                collab_type=collab_type,
                status=status,
                scheduled_date=scheduled_date,
                completed_date=completed_date,
                their_channel=or_none(request.form.get('their_channel', '')),
                their_platform=platform,
                audience_size=audience_size,
                result_views=result_views,
                result_new_subs=result_new_subs,
                result_notes=or_none(request.form.get('result_notes', '')),
                follow_up_needed=request.form.get('follow_up_needed') == 'yes',
                follow_up_date=follow_up_date,
                notes=or_none(request.form.get('notes', '')),
            )

            db.session.add(collab)
            db.session.commit()
            flash('Collaboration created successfully.', 'success')
            return redirect(url_for('collabs.list_collabs'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('collabs/form.html', collab=None, contacts=contacts)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('collabs/form.html', collab=None, contacts=contacts)

    contacts = Contact.query.order_by(Contact.name).all()
    return render_template('collabs/form.html', collab=None, contacts=contacts)


@collabs_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_collab(id):
    """Edit an existing collaboration."""
    collab = Collaboration.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Validate contact
            contact_id = validate_foreign_key(Contact, request.form.get('contact_id'), 'Contact')
            if not contact_id:
                raise ValidationError('Contact', 'This field is required.')

            # Validate choices
            collab_type = request.form.get('collab_type', 'collab_video')
            if collab_type not in COLLAB_TYPE_CHOICES:
                collab_type = 'collab_video'

            status = request.form.get('status', 'idea')
            if status not in COLLAB_STATUS_CHOICES:
                status = 'idea'

            platform = or_none(request.form.get('their_platform', ''))
            if platform and platform not in PLATFORM_CHOICES:
                platform = 'other'

            # Parse dates
            scheduled_date = parse_date(request.form.get('scheduled_date', ''), 'Scheduled Date')
            completed_date = parse_date(request.form.get('completed_date', ''), 'Completed Date')
            follow_up_date = parse_date(request.form.get('follow_up_date', ''), 'Follow-up Date')

            # Parse numbers
            audience_size = parse_int(request.form.get('audience_size', ''), 'Audience Size')
            result_views = parse_int(request.form.get('result_views', ''), 'Result Views')
            result_new_subs = parse_int(request.form.get('result_new_subs', ''), 'New Subscribers')

            collab.contact_id = contact_id
            collab.collab_type = collab_type
            collab.status = status
            collab.scheduled_date = scheduled_date
            collab.completed_date = completed_date
            collab.their_channel = or_none(request.form.get('their_channel', ''))
            collab.their_platform = platform
            collab.audience_size = audience_size
            collab.result_views = result_views
            collab.result_new_subs = result_new_subs
            collab.result_notes = or_none(request.form.get('result_notes', ''))
            collab.follow_up_needed = request.form.get('follow_up_needed') == 'yes'
            collab.follow_up_date = follow_up_date
            collab.notes = or_none(request.form.get('notes', ''))

            db.session.commit()
            flash('Collaboration updated successfully.', 'success')
            return redirect(url_for('collabs.list_collabs'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('collabs/form.html', collab=collab, contacts=contacts)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('collabs/form.html', collab=collab, contacts=contacts)

    contacts = Contact.query.order_by(Contact.name).all()
    return render_template('collabs/form.html', collab=collab, contacts=contacts)


@collabs_bp.route('/<int:id>/delete', methods=['POST'])
def delete_collab(id):
    """Delete a collaboration."""
    try:
        collab = Collaboration.query.get_or_404(id)
        db.session.delete(collab)
        db.session.commit()
        flash('Collaboration deleted.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
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
    except SQLAlchemyError:
        db.session.rollback()
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
    except SQLAlchemyError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('collabs.list_collabs'))
