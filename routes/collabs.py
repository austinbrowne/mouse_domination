from flask_login import login_required
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Collaboration, Contact
from app import db
from constants import COLLAB_STATUS_CHOICES, PLATFORM_CHOICES, DEFAULT_PAGE_SIZE
from services.options import get_choices_for_type, get_valid_values_for_type
from utils.validation import ValidationError
from utils.routes import FormData, make_delete_view, quick_action
from utils.logging import log_exception
from utils.queries import get_contacts_for_dropdown

collabs_bp = Blueprint('collabs', __name__)


@collabs_bp.route('/')
@login_required
def list_collabs():
    """List all collaborations with optional filtering and pagination."""
    collab_type = request.args.get('type')
    status = request.args.get('status')
    follow_up = request.args.get('follow_up')
    search = request.args.get('search', '').strip()[:100]  # Max 100 chars
    page = request.args.get('page', 1, type=int)

    # Get valid values for filtering (includes custom options)
    valid_collab_types = get_valid_values_for_type('collab_type')

    # Eager load contact to avoid N+1
    query = Collaboration.query.options(joinedload(Collaboration.contact))

    if collab_type and collab_type in valid_collab_types:
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
@login_required
def new_collab():
    """Create a new collaboration."""
    # Get dynamic choices for form
    collab_type_choices = get_choices_for_type('collab_type')
    valid_collab_types = [v for v, _ in collab_type_choices]

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
                collab_type=form.choice('collab_type', valid_collab_types, default='collab_video'),
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
            return render_template('collabs/form.html', collab=None, contacts=contacts,
                                   collab_type_choices=collab_type_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            contacts = get_contacts_for_dropdown()
            return render_template('collabs/form.html', collab=None, contacts=contacts,
                                   collab_type_choices=collab_type_choices)

    contacts = get_contacts_for_dropdown()
    return render_template('collabs/form.html', collab=None, contacts=contacts,
                           collab_type_choices=collab_type_choices)


@collabs_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_collab(id):
    """Edit an existing collaboration."""
    collab = Collaboration.query.options(joinedload(Collaboration.contact)).get_or_404(id)

    # Get dynamic choices for form
    collab_type_choices = get_choices_for_type('collab_type')
    valid_collab_types = [v for v, _ in collab_type_choices]

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
            collab.collab_type = form.choice('collab_type', valid_collab_types, default='collab_video')
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
            return render_template('collabs/form.html', collab=collab, contacts=contacts,
                                   collab_type_choices=collab_type_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            contacts = get_contacts_for_dropdown()
            return render_template('collabs/form.html', collab=collab, contacts=contacts,
                                   collab_type_choices=collab_type_choices)

    contacts = get_contacts_for_dropdown()
    return render_template('collabs/form.html', collab=collab, contacts=contacts,
                           collab_type_choices=collab_type_choices)


# Use generic delete view factory
collabs_bp.add_url_rule(
    '/<int:id>/delete',
    'delete_collab',
    make_delete_view(Collaboration, 'contact', 'collabs.list_collabs', 'Collaboration'),
    methods=['POST']
)


@collabs_bp.route('/<int:id>/complete', methods=['POST'])
@quick_action(Collaboration, 'collabs.list_collabs')
def complete_collab(collab):
    """Quick action to mark a collaboration as completed."""
    collab.status = 'completed'
    collab.completed_date = db.func.current_date()
    return 'Collaboration marked as completed.'


@collabs_bp.route('/<int:id>/clear-followup', methods=['POST'])
@quick_action(Collaboration, 'collabs.list_collabs')
def clear_followup(collab):
    """Clear follow-up flag."""
    collab.follow_up_needed = False
    collab.follow_up_date = None
    return 'Follow-up cleared.'
