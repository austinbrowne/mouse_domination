from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import AffiliateRevenue, Company
from app import db
from datetime import datetime
from sqlalchemy import func

affiliates_bp = Blueprint('affiliates', __name__)


@affiliates_bp.route('/')
def list_revenue():
    """List affiliate revenue with stats."""
    year = request.args.get('year', type=int)
    company_id = request.args.get('company_id', type=int)

    query = AffiliateRevenue.query

    if year:
        query = query.filter_by(year=year)
    if company_id:
        query = query.filter_by(company_id=company_id)

    entries = query.order_by(AffiliateRevenue.year.desc(), AffiliateRevenue.month.desc()).all()

    # Get available years for filter
    years = db.session.query(AffiliateRevenue.year).distinct().order_by(AffiliateRevenue.year.desc()).all()
    years = [y[0] for y in years]

    # Stats
    total_revenue = sum(e.revenue for e in entries)

    # Revenue by company
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
        entries=entries,
        years=years,
        current_year=year,
        current_company_id=company_id,
        total_revenue=total_revenue,
        revenue_by_company=revenue_by_company,
        monthly_totals=monthly_totals,
        companies=companies,
    )


@affiliates_bp.route('/new', methods=['GET', 'POST'])
def new_revenue():
    """Create a new revenue entry."""
    if request.method == 'POST':
        company_id = request.form.get('company_id')
        year = int(request.form['year'])
        month = int(request.form['month'])

        # Check for existing entry
        existing = AffiliateRevenue.query.filter_by(
            company_id=company_id, year=year, month=month
        ).first()

        if existing:
            flash(f'Revenue entry for this company/month already exists. Edit it instead.', 'error')
            companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
            current_year = datetime.now().year
            current_month = datetime.now().month
            return render_template('affiliates/form.html', entry=None, companies=companies,
                                  current_year=current_year, current_month=current_month)

        entry = AffiliateRevenue(
            company_id=company_id,
            year=year,
            month=month,
            revenue=float(request.form['revenue']),
            sales_count=int(request.form['sales_count']) if request.form.get('sales_count') else None,
            notes=request.form.get('notes') or None,
        )

        db.session.add(entry)
        db.session.commit()
        flash(f'Revenue entry created successfully.', 'success')
        return redirect(url_for('affiliates.list_revenue'))

    companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
    current_year = datetime.now().year
    current_month = datetime.now().month

    return render_template('affiliates/form.html', entry=None, companies=companies,
                          current_year=current_year, current_month=current_month)


@affiliates_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_revenue(id):
    """Edit an existing revenue entry."""
    entry = AffiliateRevenue.query.get_or_404(id)

    if request.method == 'POST':
        entry.revenue = float(request.form['revenue'])
        entry.sales_count = int(request.form['sales_count']) if request.form.get('sales_count') else None
        entry.notes = request.form.get('notes') or None

        db.session.commit()
        flash(f'Revenue entry updated successfully.', 'success')
        return redirect(url_for('affiliates.list_revenue'))

    companies = Company.query.filter(Company.affiliate_status == 'yes').order_by(Company.name).all()
    return render_template('affiliates/form.html', entry=entry, companies=companies,
                          current_year=None, current_month=None)


@affiliates_bp.route('/<int:id>/delete', methods=['POST'])
def delete_revenue(id):
    """Delete a revenue entry."""
    entry = AffiliateRevenue.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    flash('Revenue entry deleted.', 'success')
    return redirect(url_for('affiliates.list_revenue'))
