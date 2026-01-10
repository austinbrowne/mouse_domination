from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Company
from app import db
from utils.validation import (
    parse_float, validate_required, validate_url, validate_range,
    or_none, ValidationError
)

companies_bp = Blueprint('companies', __name__)

CATEGORY_CHOICES = ['mice', 'keyboards', 'mousepads', 'iems', 'other']
STATUS_CHOICES = ['no_contact', 'reached_out', 'active', 'affiliate_only', 'past']
PRIORITY_CHOICES = ['target', 'active', 'low']
AFFILIATE_STATUS_CHOICES = ['yes', 'no', 'pending']


@companies_bp.route('/')
def list_companies():
    """List all companies with optional filtering."""
    category = request.args.get('category')
    status = request.args.get('status')
    priority = request.args.get('priority')
    search = request.args.get('search', '').strip()

    query = Company.query

    if category and category in CATEGORY_CHOICES:
        query = query.filter_by(category=category)
    if status and status in STATUS_CHOICES:
        query = query.filter_by(relationship_status=status)
    if priority and priority in PRIORITY_CHOICES:
        query = query.filter_by(priority=priority)
    if search:
        query = query.filter(Company.name.ilike('%' + search + '%'))

    companies = query.order_by(Company.name).all()

    return render_template('companies/list.html',
        companies=companies,
        current_category=category,
        current_status=status,
        current_priority=priority,
        search=search,
    )


@companies_bp.route('/new', methods=['GET', 'POST'])
def new_company():
    """Create a new company."""
    if request.method == 'POST':
        try:
            # Validate required fields
            name = validate_required(request.form.get('name', ''), 'Company Name')

            # Check for duplicate
            existing = Company.query.filter_by(name=name).first()
            if existing:
                flash(f'Company "{name}" already exists.', 'error')
                return render_template('companies/form.html', company=None)

            # Validate choices
            category = request.form.get('category', 'mice')
            if category not in CATEGORY_CHOICES:
                category = 'mice'

            status = request.form.get('relationship_status', 'no_contact')
            if status not in STATUS_CHOICES:
                status = 'no_contact'

            priority = request.form.get('priority', 'low')
            if priority not in PRIORITY_CHOICES:
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
            return render_template('companies/form.html', company=None)

    return render_template('companies/form.html', company=None)


@companies_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_company(id):
    """Edit an existing company."""
    company = Company.query.get_or_404(id)

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
                return render_template('companies/form.html', company=company)

            # Validate choices
            category = request.form.get('category', 'mice')
            if category not in CATEGORY_CHOICES:
                category = 'mice'

            status = request.form.get('relationship_status', 'no_contact')
            if status not in STATUS_CHOICES:
                status = 'no_contact'

            priority = request.form.get('priority', 'low')
            if priority not in PRIORITY_CHOICES:
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
            return render_template('companies/form.html', company=company)

    return render_template('companies/form.html', company=company)


@companies_bp.route('/<int:id>/delete', methods=['POST'])
def delete_company(id):
    """Delete a company."""
    company = Company.query.get_or_404(id)
    name = company.name
    db.session.delete(company)
    db.session.commit()
    flash(f'Company "{name}" deleted.', 'success')
    return redirect(url_for('companies.list_companies'))
