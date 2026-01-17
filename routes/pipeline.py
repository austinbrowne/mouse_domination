from datetime import date, datetime, timezone
from flask_login import login_required, current_user
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, abort, jsonify
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import SalesPipeline, Company, Contact, AffiliateRevenue, DealDeliverable
from extensions import db
from constants import DEAL_STATUS_CHOICES, PAYMENT_STATUS_CHOICES, DEFAULT_PAGE_SIZE
from services.options import get_choices_for_type, get_valid_values_for_type
from utils.validation import ValidationError
from utils.routes import FormData, make_delete_view, quick_action
from utils.logging import log_exception
from utils.queries import get_companies_for_dropdown, get_contacts_for_dropdown

pipeline_bp = Blueprint('pipeline', __name__)


@pipeline_bp.route('/')
@login_required
def list_deals():
    """List all deals with optional filtering and pagination."""
    deal_type = request.args.get('type')
    status = request.args.get('status')
    payment = request.args.get('payment')
    follow_up = request.args.get('follow_up')
    page = request.args.get('page', 1, type=int)

    # Get valid values for filtering (includes custom options)
    valid_deal_types = get_valid_values_for_type('deal_type')

    # Eager load relationships to avoid N+1
    # Filter by current user for data isolation
    query = SalesPipeline.query.options(
        joinedload(SalesPipeline.company),
        joinedload(SalesPipeline.contact)
    ).filter_by(user_id=current_user.id)

    if deal_type and deal_type in valid_deal_types:
        query = query.filter_by(deal_type=deal_type)
    if status and status in DEAL_STATUS_CHOICES:
        query = query.filter_by(status=status)
    if payment and payment in PAYMENT_STATUS_CHOICES:
        query = query.filter_by(payment_status=payment)
    if follow_up == 'yes':
        query = query.filter_by(follow_up_needed=True)

    # Paginated query
    pagination = query.order_by(SalesPipeline.created_at.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Stats using database aggregation - compute what the template expects (user's data only)
    stats_query = db.session.query(
        func.sum(func.cast(SalesPipeline.status == 'lead', db.Integer)).label('lead'),
        func.sum(func.cast(SalesPipeline.status == 'negotiating', db.Integer)).label('negotiating'),
        func.coalesce(func.sum(
            func.cast(SalesPipeline.status == 'completed', db.Integer) *
            func.coalesce(SalesPipeline.rate_agreed, 0)
        ), 0).label('total_revenue'),
        func.coalesce(func.sum(
            func.cast(SalesPipeline.status.in_(['lead', 'negotiating', 'confirmed']), db.Integer) *
            func.coalesce(SalesPipeline.rate_quoted, 0)
        ), 0).label('pipeline_value'),
    ).filter(SalesPipeline.user_id == current_user.id).first()

    stats = {
        'lead': stats_query.lead or 0,
        'negotiating': stats_query.negotiating or 0,
        'total_revenue': stats_query.total_revenue or 0,
        'pipeline_value': stats_query.pipeline_value or 0,
    }

    companies = get_companies_for_dropdown()
    contacts = get_contacts_for_dropdown()

    return render_template('pipeline/list.html',
        deals=pagination.items,
        pagination=pagination,
        companies=companies,
        contacts=contacts,
        current_type=deal_type,
        current_status=status,
        current_payment=payment,
        current_follow_up=follow_up,
        stats=stats,
    )


@pipeline_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_deal():
    """Create a new deal."""
    # Get dynamic choices for form
    deal_type_choices = get_choices_for_type('deal_type')
    valid_deal_types = [v for v, _ in deal_type_choices]

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Validate required company
            company_id = form.foreign_key('company_id', Company)
            if not company_id:
                raise ValidationError('Company', 'This field is required.')

            deal = SalesPipeline(
                user_id=current_user.id,
                company_id=company_id,
                contact_id=form.foreign_key('contact_id', Contact),
                deal_type=form.choice('deal_type', valid_deal_types, default='paid_review'),
                status=form.choice('status', DEAL_STATUS_CHOICES, default='lead'),
                rate_quoted=form.decimal('rate_quoted'),
                rate_agreed=form.decimal('rate_agreed'),
                deliverables=form.optional('deliverables'),
                deadline=form.date('deadline'),
                deliverable_date=form.date('deliverable_date'),
                payment_status=form.choice('payment_status', PAYMENT_STATUS_CHOICES, default='pending'),
                payment_date=form.date('payment_date'),
                notes=form.optional('notes'),
                follow_up_needed=form.boolean('follow_up_needed'),
                follow_up_date=form.date('follow_up_date'),
            )

            db.session.add(deal)
            db.session.commit()
            flash('Deal created successfully.', 'success')
            return redirect(url_for('pipeline.list_deals'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            contacts = get_contacts_for_dropdown()
            return render_template('pipeline/form.html', deal=None, companies=companies, contacts=contacts,
                                   deal_type_choices=deal_type_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            contacts = get_contacts_for_dropdown()
            return render_template('pipeline/form.html', deal=None, companies=companies, contacts=contacts,
                                   deal_type_choices=deal_type_choices)

    companies = get_companies_for_dropdown()
    contacts = get_contacts_for_dropdown()
    return render_template('pipeline/form.html', deal=None, companies=companies, contacts=contacts,
                           deal_type_choices=deal_type_choices)


@pipeline_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_deal(id):
    """Edit an existing deal."""
    deal = SalesPipeline.query.options(
        joinedload(SalesPipeline.company),
        joinedload(SalesPipeline.contact)
    ).get_or_404(id)
    # Verify ownership
    if deal.user_id != current_user.id:
        abort(403)

    # Get dynamic choices for form
    deal_type_choices = get_choices_for_type('deal_type')
    valid_deal_types = [v for v, _ in deal_type_choices]

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Validate required company
            company_id = form.foreign_key('company_id', Company)
            if not company_id:
                raise ValidationError('Company', 'This field is required.')

            deal.company_id = company_id
            deal.contact_id = form.foreign_key('contact_id', Contact)
            deal.deal_type = form.choice('deal_type', valid_deal_types, default='paid_review')
            deal.status = form.choice('status', DEAL_STATUS_CHOICES, default='lead')
            deal.rate_quoted = form.decimal('rate_quoted')
            deal.rate_agreed = form.decimal('rate_agreed')
            deal.deliverables = form.optional('deliverables')
            deal.deadline = form.date('deadline')
            deal.deliverable_date = form.date('deliverable_date')
            deal.payment_status = form.choice('payment_status', PAYMENT_STATUS_CHOICES, default='pending')
            deal.payment_date = form.date('payment_date')
            deal.notes = form.optional('notes')
            deal.follow_up_needed = form.boolean('follow_up_needed')
            deal.follow_up_date = form.date('follow_up_date')

            db.session.commit()
            flash('Deal updated successfully.', 'success')
            return redirect(url_for('pipeline.list_deals'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            contacts = get_contacts_for_dropdown()
            return render_template('pipeline/form.html', deal=deal, companies=companies, contacts=contacts,
                                   deal_type_choices=deal_type_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            contacts = get_contacts_for_dropdown()
            return render_template('pipeline/form.html', deal=deal, companies=companies, contacts=contacts,
                                   deal_type_choices=deal_type_choices)

    companies = get_companies_for_dropdown()
    contacts = get_contacts_for_dropdown()
    return render_template('pipeline/form.html', deal=deal, companies=companies, contacts=contacts,
                           deal_type_choices=deal_type_choices)


# Use generic delete view factory with user ownership check
pipeline_bp.add_url_rule(
    '/<int:id>/delete',
    'delete_deal',
    make_delete_view(SalesPipeline, 'deliverables', 'pipeline.list_deals', 'Deal', check_user_id=True),
    methods=['POST']
)


@pipeline_bp.route('/<int:id>/mark-complete', methods=['POST'])
@quick_action(SalesPipeline, 'pipeline.list_deals', check_user_id=True)
def mark_complete(deal):
    """Quick action to mark a deal as completed.

    If deal is paid with an agreed rate, auto-creates an affiliate revenue entry.
    """
    deal.status = 'completed'

    # Auto-create revenue entry if fully paid with agreed rate
    if deal.payment_status == 'paid' and deal.rate_agreed and deal.company_id:
        today = date.today()

        # Check if entry already exists for this user/company/month
        existing = AffiliateRevenue.query.filter_by(
            user_id=deal.user_id,
            company_id=deal.company_id,
            year=today.year,
            month=today.month
        ).first()

        if existing:
            existing.revenue = (existing.revenue or 0) + deal.rate_agreed
            if existing.notes:
                existing.notes += f"\n+ Deal: {deal.deliverables or 'N/A'}"
            else:
                existing.notes = f"From deal: {deal.deliverables or 'N/A'}"
        else:
            revenue = AffiliateRevenue(
                user_id=deal.user_id,
                company_id=deal.company_id,
                year=today.year,
                month=today.month,
                revenue=deal.rate_agreed,
                notes=f"From deal: {deal.deliverables or 'N/A'}"
            )
            db.session.add(revenue)

        return 'Deal marked as completed. Revenue entry created.'

    return 'Deal marked as completed.'


@pipeline_bp.route('/<int:id>/mark-paid', methods=['POST'])
@quick_action(SalesPipeline, 'pipeline.list_deals', check_user_id=True)
def mark_paid(deal):
    """Quick action to mark a deal as paid.

    If deal is completed with an agreed rate, auto-creates an affiliate revenue entry.
    """
    deal.payment_status = 'paid'
    deal.payment_date = db.func.current_date()

    # Auto-create revenue entry if completed with agreed rate
    if deal.status == 'completed' and deal.rate_agreed and deal.company_id:
        today = date.today()

        # Check if entry already exists for this user/company/month
        existing = AffiliateRevenue.query.filter_by(
            user_id=deal.user_id,
            company_id=deal.company_id,
            year=today.year,
            month=today.month
        ).first()

        if existing:
            existing.revenue = (existing.revenue or 0) + deal.rate_agreed
            if existing.notes:
                existing.notes += f"\n+ Deal: {deal.deliverables or 'N/A'}"
            else:
                existing.notes = f"From deal: {deal.deliverables or 'N/A'}"
        else:
            revenue = AffiliateRevenue(
                user_id=deal.user_id,
                company_id=deal.company_id,
                year=today.year,
                month=today.month,
                revenue=deal.rate_agreed,
                notes=f"From deal: {deal.deliverables or 'N/A'}"
            )
            db.session.add(revenue)

        return 'Deal marked as paid. Revenue entry created.'

    return 'Deal marked as paid.'


# ---- Deal Deliverables Routes ----

@pipeline_bp.route('/<int:id>/deliverables')
@login_required
def list_deliverables(id):
    """List and manage deliverables for a deal."""
    deal = SalesPipeline.query.options(
        joinedload(SalesPipeline.company),
        joinedload(SalesPipeline.contact),
        joinedload(SalesPipeline.deliverables_list)
    ).get_or_404(id)

    if deal.user_id != current_user.id:
        abort(403)

    # Calculate stats
    total_deliverables = len(deal.deliverables_list)
    completed = sum(1 for d in deal.deliverables_list if d.status in ('delivered', 'verified'))
    overdue = sum(1 for d in deal.deliverables_list if d.is_overdue)

    # Total metrics
    total_impressions = sum(d.impressions or 0 for d in deal.deliverables_list)
    total_engagement = sum(d.engagement or 0 for d in deal.deliverables_list)
    total_clicks = sum(d.clicks or 0 for d in deal.deliverables_list)

    return render_template('pipeline/deliverables.html',
        deal=deal,
        deliverables=deal.deliverables_list,
        total_deliverables=total_deliverables,
        completed=completed,
        overdue=overdue,
        total_impressions=total_impressions,
        total_engagement=total_engagement,
        total_clicks=total_clicks,
        deliverable_types=DealDeliverable.DELIVERABLE_TYPES,
        statuses=DealDeliverable.STATUSES,
    )


@pipeline_bp.route('/<int:id>/deliverables/add', methods=['GET', 'POST'])
@login_required
def add_deliverable(id):
    """Add a new deliverable to a deal."""
    deal = SalesPipeline.query.get_or_404(id)
    if deal.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            deliverable_type = form.choice('deliverable_type',
                [t[0] for t in DealDeliverable.DELIVERABLE_TYPES],
                default=DealDeliverable.TYPE_OTHER)

            deliverable = DealDeliverable(
                deal_id=deal.id,
                deliverable_type=deliverable_type,
                description=form.optional('description'),
                due_date=form.date('due_date'),
                platform_post_url=form.optional('platform_post_url'),
                status=form.choice('status',
                    [s[0] for s in DealDeliverable.STATUSES],
                    default=DealDeliverable.STATUS_PENDING),
                notes=form.optional('notes'),
            )

            db.session.add(deliverable)
            db.session.commit()
            flash('Deliverable added successfully.', 'success')
            return redirect(url_for('pipeline.list_deliverables', id=deal.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('pipeline/deliverable_form.html',
        deal=deal,
        deliverable=None,
        deliverable_types=DealDeliverable.DELIVERABLE_TYPES,
        statuses=DealDeliverable.STATUSES,
    )


@pipeline_bp.route('/<int:id>/deliverables/<int:deliverable_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_deliverable(id, deliverable_id):
    """Edit an existing deliverable."""
    deal = SalesPipeline.query.get_or_404(id)
    if deal.user_id != current_user.id:
        abort(403)

    deliverable = DealDeliverable.query.filter_by(id=deliverable_id, deal_id=deal.id).first_or_404()

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            deliverable.deliverable_type = form.choice('deliverable_type',
                [t[0] for t in DealDeliverable.DELIVERABLE_TYPES],
                default=DealDeliverable.TYPE_OTHER)
            deliverable.description = form.optional('description')
            deliverable.due_date = form.date('due_date')
            deliverable.completed_date = form.date('completed_date')
            deliverable.platform_post_url = form.optional('platform_post_url')
            deliverable.platform_post_id = form.optional('platform_post_id')
            deliverable.impressions = form.integer('impressions')
            deliverable.reach = form.integer('reach')
            deliverable.engagement = form.integer('engagement')
            deliverable.clicks = form.integer('clicks')
            deliverable.conversions = form.integer('conversions')
            deliverable.status = form.choice('status',
                [s[0] for s in DealDeliverable.STATUSES],
                default=DealDeliverable.STATUS_PENDING)
            deliverable.notes = form.optional('notes')

            # Auto-set completed_date if status changed to delivered/verified
            if deliverable.status in ('delivered', 'verified') and not deliverable.completed_date:
                deliverable.completed_date = date.today()

            db.session.commit()
            flash('Deliverable updated successfully.', 'success')
            return redirect(url_for('pipeline.list_deliverables', id=deal.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('pipeline/deliverable_form.html',
        deal=deal,
        deliverable=deliverable,
        deliverable_types=DealDeliverable.DELIVERABLE_TYPES,
        statuses=DealDeliverable.STATUSES,
    )


@pipeline_bp.route('/<int:id>/deliverables/<int:deliverable_id>/delete', methods=['POST'])
@login_required
def delete_deliverable(id, deliverable_id):
    """Delete a deliverable."""
    deal = SalesPipeline.query.get_or_404(id)
    if deal.user_id != current_user.id:
        abort(403)

    try:
        deliverable = DealDeliverable.query.filter_by(id=deliverable_id, deal_id=deal.id).first_or_404()
        db.session.delete(deliverable)
        db.session.commit()
        flash('Deliverable deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('pipeline.list_deliverables', id=deal.id))


@pipeline_bp.route('/<int:id>/deliverables/<int:deliverable_id>/mark-delivered', methods=['POST'])
@login_required
def mark_delivered(id, deliverable_id):
    """Quick action to mark a deliverable as delivered."""
    deal = SalesPipeline.query.get_or_404(id)
    if deal.user_id != current_user.id:
        abort(403)

    try:
        deliverable = DealDeliverable.query.filter_by(id=deliverable_id, deal_id=deal.id).first_or_404()
        deliverable.status = DealDeliverable.STATUS_DELIVERED
        deliverable.completed_date = date.today()
        db.session.commit()
        flash('Deliverable marked as delivered.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('pipeline.list_deliverables', id=deal.id))


@pipeline_bp.route('/<int:id>/generate-report', methods=['POST'])
@login_required
def generate_report(id):
    """Generate a proof-of-performance report for a deal."""
    deal = SalesPipeline.query.options(
        joinedload(SalesPipeline.deliverables_list)
    ).get_or_404(id)

    if deal.user_id != current_user.id:
        abort(403)

    try:
        # Aggregate metrics from all deliverables
        total_impressions = sum(d.impressions or 0 for d in deal.deliverables_list)
        total_reach = sum(d.reach or 0 for d in deal.deliverables_list)
        total_engagement = sum(d.engagement or 0 for d in deal.deliverables_list)
        total_clicks = sum(d.clicks or 0 for d in deal.deliverables_list)
        total_conversions = sum(d.conversions or 0 for d in deal.deliverables_list)

        # Count deliverables by status
        delivered_count = sum(1 for d in deal.deliverables_list if d.status in ('delivered', 'verified'))
        total_count = len(deal.deliverables_list)

        # Build report
        deal.performance_report = {
            'total_impressions': total_impressions,
            'total_reach': total_reach,
            'total_engagement': total_engagement,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'deliverables_completed': delivered_count,
            'deliverables_total': total_count,
            'generated_at': datetime.now(timezone.utc).isoformat(),
        }
        deal.report_generated_at = datetime.now(timezone.utc)

        db.session.commit()
        flash('Performance report generated successfully.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Generate report', e)
        flash('Error generating report. Please try again.', 'error')

    return redirect(url_for('pipeline.list_deliverables', id=deal.id))
