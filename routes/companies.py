from flask_login import login_required
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import SQLAlchemyError
from models import Company
from app import db
from constants import (
    COMPANY_STATUS_CHOICES, COMPANY_PRIORITY_CHOICES, AFFILIATE_STATUS_CHOICES, DEFAULT_PAGE_SIZE
)
from services.crud import CompanyService
from services.options import get_choices_for_type, get_valid_values_for_type
from utils.validation import (
    parse_float, validate_required, validate_url, validate_range,
    or_none, ValidationError
)
from utils.logging import log_exception

companies_bp = Blueprint('companies', __name__)


@companies_bp.route('/')
@login_required
def list_companies():
    """List all companies with optional filtering."""
    category = request.args.get('category')
    status = request.args.get('status')
    priority = request.args.get('priority')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # Get valid values for filtering (includes custom options)
    valid_categories = get_valid_values_for_type('company_category')

    # Build filters dict
    filters = {}
    if category and category in valid_categories:
        filters['category'] = category
    if status and status in COMPANY_STATUS_CHOICES:
        filters['relationship_status'] = status
    if priority and priority in COMPANY_PRIORITY_CHOICES:
        filters['priority'] = priority

    # Use service layer for efficient query with counts
    results = CompanyService.list_with_counts(filters=filters, search=search)

    # Build company list with counts
    companies_with_counts = [
        {'company': c, 'contact_count': cc, 'inventory_count': ic}
        for c, cc, ic in results
    ]

    return render_template('companies/list.html',
        companies_with_counts=companies_with_counts,
        current_category=category,
        current_status=status,
        current_priority=priority,
        search=search,
    )


@companies_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_company():
    """Create a new company."""
    # Get dynamic choices for form
    category_choices = get_choices_for_type('company_category')
    valid_categories = [v for v, _ in category_choices]

    if request.method == 'POST':
        try:
            # Validate required fields
            name = validate_required(request.form.get('name', ''), 'Company Name')

            # Check for duplicate
            existing = Company.query.filter_by(name=name).first()
            if existing:
                flash(f'Company "{name}" already exists.', 'error')
                return render_template('companies/form.html', company=None,
                                       category_choices=category_choices)

            # Validate choices using dynamic values
            category = request.form.get('category', 'mice')
            if category not in valid_categories:
                category = 'mice'

            status = request.form.get('relationship_status', 'no_contact')
            if status not in COMPANY_STATUS_CHOICES:
                status = 'no_contact'

            priority = request.form.get('priority', 'low')
            if priority not in COMPANY_PRIORITY_CHOICES:
                priority = 'low'

            affiliate_status = request.form.get('affiliate_status', 'no')
            if affiliate_status not in AFFILIATE_STATUS_CHOICES:
                affiliate_status = 'no'

            # Validate URL
            website = validate_url(request.form.get('website', ''), 'Website')
            affiliate_link = validate_url(request.form.get('affiliate_link', ''), 'Affiliate Link')

            # Validate commission rate
            commission_rate = parse_float(request.form.get('commission_rate', ''), 'Commission Rate')
            if commission_rate is not None:
                validate_range(commission_rate, 0, 100, 'Commission Rate')

            company = Company(
                name=name,
                category=category,
                website=website,
                relationship_status=status,
                affiliate_status=affiliate_status,
                affiliate_code=or_none(request.form.get('affiliate_code', '')),
                affiliate_link=affiliate_link,
                commission_rate=commission_rate,
                notes=or_none(request.form.get('notes', '')),
                priority=priority,
            )

            db.session.add(company)
            db.session.commit()
            flash(f'Company "{company.name}" created successfully.', 'success')
            return redirect(url_for('companies.list_companies'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('companies/form.html', company=None,
                                   category_choices=category_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('companies/form.html', company=None,
                                   category_choices=category_choices)

    return render_template('companies/form.html', company=None,
                           category_choices=category_choices)


@companies_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_company(id):
    """Edit an existing company."""
    company = Company.query.get_or_404(id)

    # Get dynamic choices for form
    category_choices = get_choices_for_type('company_category')
    valid_categories = [v for v, _ in category_choices]

    if request.method == 'POST':
        try:
            # Validate required fields
            name = validate_required(request.form.get('name', ''), 'Company Name')

            # Check for duplicate name (excluding current)
            existing = Company.query.filter(
                Company.name == name,
                Company.id != id
            ).first()
            if existing:
                flash(f'Company "{name}" already exists.', 'error')
                return render_template('companies/form.html', company=company,
                                       category_choices=category_choices)

            # Validate choices using dynamic values
            category = request.form.get('category', 'mice')
            if category not in valid_categories:
                category = 'mice'

            status = request.form.get('relationship_status', 'no_contact')
            if status not in COMPANY_STATUS_CHOICES:
                status = 'no_contact'

            priority = request.form.get('priority', 'low')
            if priority not in COMPANY_PRIORITY_CHOICES:
                priority = 'low'

            affiliate_status = request.form.get('affiliate_status', 'no')
            if affiliate_status not in AFFILIATE_STATUS_CHOICES:
                affiliate_status = 'no'

            # Validate URL
            website = validate_url(request.form.get('website', ''), 'Website')
            affiliate_link = validate_url(request.form.get('affiliate_link', ''), 'Affiliate Link')

            # Validate commission rate
            commission_rate = parse_float(request.form.get('commission_rate', ''), 'Commission Rate')
            if commission_rate is not None:
                validate_range(commission_rate, 0, 100, 'Commission Rate')

            company.name = name
            company.category = category
            company.website = website
            company.relationship_status = status
            company.affiliate_status = affiliate_status
            company.affiliate_code = or_none(request.form.get('affiliate_code', ''))
            company.affiliate_link = affiliate_link
            company.commission_rate = commission_rate
            company.notes = or_none(request.form.get('notes', ''))
            company.priority = priority

            db.session.commit()
            flash(f'Company "{company.name}" updated successfully.', 'success')
            return redirect(url_for('companies.list_companies'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('companies/form.html', company=company,
                                   category_choices=category_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('companies/form.html', company=company,
                                   category_choices=category_choices)

    return render_template('companies/form.html', company=company,
                           category_choices=category_choices)


@companies_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_company(id):
    """Delete a company."""
    try:
        company = Company.query.get_or_404(id)
        name = company.name
        db.session.delete(company)
        db.session.commit()
        flash(f'Company "{name}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('companies.list_companies'))
