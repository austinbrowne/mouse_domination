from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import SalesPipeline, Company, Contact
from app import db
from constants import (
    DEAL_TYPE_CHOICES, DEAL_STATUS_CHOICES, PAYMENT_STATUS_CHOICES, DEFAULT_PAGE_SIZE
)
from utils.validation import (
    parse_date, parse_float, validate_required, validate_foreign_key,
    validate_choice, or_none, ValidationError
)

pipeline_bp = Blueprint('pipeline', __name__)


@pipeline_bp.route('/')
def list_deals():
    """List all deals with optional filtering and pagination."""
    deal_type = request.args.get('type')
    status = request.args.get('status')
    payment = request.args.get('payment')
    follow_up = request.args.get('follow_up')
    page = request.args.get('page', 1, type=int)

    # Eager load relationships to avoid N+1
    query = SalesPipeline.query.options(
        joinedload(SalesPipeline.company),
        joinedload(SalesPipeline.contact)
    )

    if deal_type and deal_type in DEAL_TYPE_CHOICES:
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

    # Stats using database aggregation
    stats = db.session.query(
        func.count(SalesPipeline.id).label('total'),
        func.sum(func.cast(SalesPipeline.status.in_(['lead', 'negotiating', 'confirmed']), db.Integer)).label('active'),
        func.sum(func.cast(SalesPipeline.status == 'completed', db.Integer)).label('completed'),
        func.coalesce(func.sum(
            func.cast(SalesPipeline.status == 'completed', db.Integer) *
            func.coalesce(SalesPipeline.rate_agreed, 0)
        ), 0).label('total_revenue'),
        func.coalesce(func.sum(
            func.cast(SalesPipeline.status.in_(['lead', 'negotiating', 'confirmed']), db.Integer) *
            func.coalesce(SalesPipeline.rate_quoted, 0)
        ), 0).label('pipeline_value'),
    ).first()

    companies = Company.query.order_by(Company.name).all()
    contacts = Contact.query.order_by(Contact.name).all()

    return render_template('pipeline/list.html',
        deals=pagination.items,
        pagination=pagination,
        companies=companies,
        contacts=contacts,
        current_type=deal_type,
        current_status=status,
        current_payment=payment,
        current_follow_up=follow_up,
        total=stats.total or 0,
        active=stats.active or 0,
        completed=stats.completed or 0,
        total_revenue=stats.total_revenue or 0,
        pipeline_value=stats.pipeline_value or 0,
    )


@pipeline_bp.route('/new', methods=['GET', 'POST'])
def new_deal():
    """Create a new deal."""
    if request.method == 'POST':
        try:
            # Validate company
            company_id = validate_foreign_key(Company, request.form.get('company_id'), 'Company')
            if not company_id:
                raise ValidationError('Company', 'This field is required.')

            # Validate contact (optional)
            contact_id = validate_foreign_key(Contact, request.form.get('contact_id'), 'Contact')

            # Validate choices
            deal_type = request.form.get('deal_type', 'paid_review')
            if deal_type not in DEAL_TYPE_CHOICES:
                deal_type = 'paid_review'

            status = request.form.get('status', 'lead')
            if status not in DEAL_STATUS_CHOICES:
                status = 'lead'

            payment_status = request.form.get('payment_status', 'pending')
            if payment_status not in PAYMENT_STATUS_CHOICES:
                payment_status = 'pending'

            # Parse numbers
            rate_quoted = parse_float(request.form.get('rate_quoted', ''), 'Rate Quoted')
            rate_agreed = parse_float(request.form.get('rate_agreed', ''), 'Rate Agreed')

            # Parse dates
            deadline = parse_date(request.form.get('deadline', ''), 'Deadline')
            payment_date = parse_date(request.form.get('payment_date', ''), 'Payment Date')
            follow_up_date = parse_date(request.form.get('follow_up_date', ''), 'Follow-up Date')

            deal = SalesPipeline(
                company_id=company_id,
                contact_id=contact_id,
                deal_type=deal_type,
                status=status,
                rate_quoted=rate_quoted,
                rate_agreed=rate_agreed,
                deliverables=or_none(request.form.get('deliverables', '')),
                deadline=deadline,
                payment_status=payment_status,
                payment_date=payment_date,
                notes=or_none(request.form.get('notes', '')),
                follow_up_needed=request.form.get('follow_up_needed') == 'yes',
                follow_up_date=follow_up_date,
            )

            db.session.add(deal)
            db.session.commit()
            flash('Deal created successfully.', 'success')
            return redirect(url_for('pipeline.list_deals'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.order_by(Company.name).all()
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('pipeline/form.html', deal=None, companies=companies, contacts=contacts)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.order_by(Company.name).all()
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('pipeline/form.html', deal=None, companies=companies, contacts=contacts)

    companies = Company.query.order_by(Company.name).all()
    contacts = Contact.query.order_by(Contact.name).all()
    return render_template('pipeline/form.html', deal=None, companies=companies, contacts=contacts)


@pipeline_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_deal(id):
    """Edit an existing deal."""
    deal = SalesPipeline.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Validate company
            company_id = validate_foreign_key(Company, request.form.get('company_id'), 'Company')
            if not company_id:
                raise ValidationError('Company', 'This field is required.')

            # Validate contact (optional)
            contact_id = validate_foreign_key(Contact, request.form.get('contact_id'), 'Contact')

            # Validate choices
            deal_type = request.form.get('deal_type', 'paid_review')
            if deal_type not in DEAL_TYPE_CHOICES:
                deal_type = 'paid_review'

            status = request.form.get('status', 'lead')
            if status not in DEAL_STATUS_CHOICES:
                status = 'lead'

            payment_status = request.form.get('payment_status', 'pending')
            if payment_status not in PAYMENT_STATUS_CHOICES:
                payment_status = 'pending'

            # Parse numbers
            rate_quoted = parse_float(request.form.get('rate_quoted', ''), 'Rate Quoted')
            rate_agreed = parse_float(request.form.get('rate_agreed', ''), 'Rate Agreed')

            # Parse dates
            deadline = parse_date(request.form.get('deadline', ''), 'Deadline')
            payment_date = parse_date(request.form.get('payment_date', ''), 'Payment Date')
            follow_up_date = parse_date(request.form.get('follow_up_date', ''), 'Follow-up Date')

            deal.company_id = company_id
            deal.contact_id = contact_id
            deal.deal_type = deal_type
            deal.status = status
            deal.rate_quoted = rate_quoted
            deal.rate_agreed = rate_agreed
            deal.deliverables = or_none(request.form.get('deliverables', ''))
            deal.deadline = deadline
            deal.payment_status = payment_status
            deal.payment_date = payment_date
            deal.notes = or_none(request.form.get('notes', ''))
            deal.follow_up_needed = request.form.get('follow_up_needed') == 'yes'
            deal.follow_up_date = follow_up_date

            db.session.commit()
            flash('Deal updated successfully.', 'success')
            return redirect(url_for('pipeline.list_deals'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.order_by(Company.name).all()
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('pipeline/form.html', deal=deal, companies=companies, contacts=contacts)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.order_by(Company.name).all()
            contacts = Contact.query.order_by(Contact.name).all()
            return render_template('pipeline/form.html', deal=deal, companies=companies, contacts=contacts)

    companies = Company.query.order_by(Company.name).all()
    contacts = Contact.query.order_by(Contact.name).all()
    return render_template('pipeline/form.html', deal=deal, companies=companies, contacts=contacts)


@pipeline_bp.route('/<int:id>/delete', methods=['POST'])
def delete_deal(id):
    """Delete a deal."""
    try:
        deal = SalesPipeline.query.get_or_404(id)
        db.session.delete(deal)
        db.session.commit()
        flash('Deal deleted.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('pipeline.list_deals'))


@pipeline_bp.route('/<int:id>/mark-complete', methods=['POST'])
def mark_complete(id):
    """Quick action to mark a deal as completed."""
    try:
        deal = SalesPipeline.query.get_or_404(id)
        deal.status = 'completed'
        db.session.commit()
        flash('Deal marked as completed.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('pipeline.list_deals'))


@pipeline_bp.route('/<int:id>/mark-paid', methods=['POST'])
def mark_paid(id):
    """Quick action to mark a deal as paid."""
    try:
        deal = SalesPipeline.query.get_or_404(id)
        deal.payment_status = 'paid'
        deal.payment_date = db.func.current_date()
        db.session.commit()
        flash('Deal marked as paid.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('pipeline.list_deals'))
