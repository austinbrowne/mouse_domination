from flask_login import login_required
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import AffiliateRevenue, Company
from app import db
from datetime import datetime
from constants import DEFAULT_PAGE_SIZE
from utils.validation import (
    parse_float, parse_int, validate_required, validate_foreign_key, validate_range,
    or_none, ValidationError
)
from utils.logging import log_exception

affiliates_bp = Blueprint('affiliates', __name__)


@affiliates_bp.route('/')
@login_required
def list_revenue():
    """List affiliate revenue with stats and pagination."""
    year = request.args.get('year', type=int)
    company_id = request.args.get('company_id', type=int)
    page = request.args.get('page', 1, type=int)

    # Eager load company to avoid N+1
    query = AffiliateRevenue.query.options(joinedload(AffiliateRevenue.company))

    if year:
        query = query.filter_by(year=year)
    if company_id:
        query = query.filter_by(company_id=company_id)

    # Paginated query
    pagination = query.order_by(
        AffiliateRevenue.year.desc(), AffiliateRevenue.month.desc()
    ).paginate(page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False)

    # Get available years for filter
    years = db.session.query(AffiliateRevenue.year).distinct().order_by(AffiliateRevenue.year.desc()).all()
    years = [y[0] for y in years]

    # Stats - use database aggregation
    total_revenue = db.session.query(func.coalesce(func.sum(AffiliateRevenue.revenue), 0)).scalar()

    # Revenue by company - single efficient query
    revenue_by_company = db.session.query(
        Company.name,
        func.sum(AffiliateRevenue.revenue).label('total')
    ).join(AffiliateRevenue).group_by(Company.name).order_by(func.sum(AffiliateRevenue.revenue).desc()).all()

    # Monthly totals for chart
    monthly_totals = db.session.query(
        AffiliateRevenue.year,
        AffiliateRevenue.month,
        func.sum(AffiliateRevenue.revenue).label('total')
    ).group_by(AffiliateRevenue.year, AffiliateRevenue.month).order_by(
        AffiliateRevenue.year, AffiliateRevenue.month
    ).all()

    companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()

    return render_template('affiliates/list.html',
        entries=pagination.items,
        pagination=pagination,
        years=years,
        current_year=year,
        current_company_id=company_id,
        total_revenue=total_revenue,
        revenue_by_company=revenue_by_company,
        monthly_totals=monthly_totals,
        companies=companies,
    )


@affiliates_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_revenue():
    """Create a new revenue entry."""
    if request.method == 'POST':
        try:
            # Validate company
            company_id = validate_foreign_key(Company, request.form.get('company_id'), 'Company')
            if not company_id:
                raise ValidationError('Company', 'This field is required.')

            # Validate year and month
            year = parse_int(request.form.get('year', ''), 'Year', allow_negative=False)
            if not year:
                raise ValidationError('Year', 'This field is required.')
            validate_range(year, 2000, 2100, 'Year')

            month = parse_int(request.form.get('month', ''), 'Month', allow_negative=False)
            if not month:
                raise ValidationError('Month', 'This field is required.')
            validate_range(month, 1, 12, 'Month')

            # Validate revenue
            revenue = parse_float(request.form.get('revenue', ''), 'Revenue', allow_negative=False)
            if revenue is None:
                raise ValidationError('Revenue', 'This field is required.')

            sales_count = parse_int(request.form.get('sales_count', ''), 'Sales Count', allow_negative=False)

            # Check for existing entry
            existing = AffiliateRevenue.query.filter_by(
                company_id=company_id, year=year, month=month
            ).first()

            if existing:
                flash('Revenue entry for this company/month already exists. Edit it instead.', 'error')
                companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
                current_year = datetime.now().year
                current_month = datetime.now().month
                return render_template('affiliates/form.html', entry=None, companies=companies,
                                      current_year=current_year, current_month=current_month)

            entry = AffiliateRevenue(
                company_id=company_id,
                year=year,
                month=month,
                revenue=revenue,
                sales_count=sales_count,
                notes=or_none(request.form.get('notes', '')),
            )

            db.session.add(entry)
            db.session.commit()
            flash('Revenue entry created successfully.', 'success')
            return redirect(url_for('affiliates.list_revenue'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
            current_year = datetime.now().year
            current_month = datetime.now().month
            return render_template('affiliates/form.html', entry=None, companies=companies,
                                  current_year=current_year, current_month=current_month)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
            current_year = datetime.now().year
            current_month = datetime.now().month
            return render_template('affiliates/form.html', entry=None, companies=companies,
                                  current_year=current_year, current_month=current_month)

    companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
    current_year = datetime.now().year
    current_month = datetime.now().month

    return render_template('affiliates/form.html', entry=None, companies=companies,
                          current_year=current_year, current_month=current_month)


@affiliates_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_revenue(id):
    """Edit an existing revenue entry."""
    entry = AffiliateRevenue.query.get_or_404(id)

    if request.method == 'POST':
        try:
            revenue = parse_float(request.form.get('revenue', ''), 'Revenue', allow_negative=False)
            if revenue is None:
                raise ValidationError('Revenue', 'This field is required.')

            sales_count = parse_int(request.form.get('sales_count', ''), 'Sales Count', allow_negative=False)

            entry.revenue = revenue
            entry.sales_count = sales_count
            entry.notes = or_none(request.form.get('notes', ''))

            db.session.commit()
            flash('Revenue entry updated successfully.', 'success')
            return redirect(url_for('affiliates.list_revenue'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
            return render_template('affiliates/form.html', entry=entry, companies=companies,
                                  current_year=None, current_month=None)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
            return render_template('affiliates/form.html', entry=entry, companies=companies,
                                  current_year=None, current_month=None)

    companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
    return render_template('affiliates/form.html', entry=entry, companies=companies,
                          current_year=None, current_month=None)


@affiliates_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_revenue(id):
    """Delete a revenue entry."""
    try:
        entry = AffiliateRevenue.query.get_or_404(id)
        db.session.delete(entry)
        db.session.commit()
        flash('Revenue entry deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('affiliates.list_revenue'))
