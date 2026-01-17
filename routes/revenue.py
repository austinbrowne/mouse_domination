"""Creator Hub: Unified Revenue Dashboard

Provides a consolidated view of all income streams:
- Sponsorships (from SalesPipeline)
- Affiliates (from AffiliateRevenue)
- Platform payouts (YouTube, TikTok, etc.)
- Digital products
- Memberships
"""
import io
import csv
from datetime import datetime, date
from decimal import Decimal
from flask_login import login_required, current_user
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, abort, Response
from sqlalchemy import func, extract
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import RevenueEntry, AffiliateRevenue, SalesPipeline, Company
from extensions import db
from constants import DEFAULT_PAGE_SIZE
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception

revenue_bp = Blueprint('revenue', __name__)


@revenue_bp.route('/')
@login_required
def dashboard():
    """Unified revenue dashboard with analytics and diversification metrics."""
    year = request.args.get('year', type=int)
    source_type = request.args.get('source_type')
    page = request.args.get('page', 1, type=int)

    # Base query for revenue entries
    query = RevenueEntry.query.filter_by(user_id=current_user.id)

    if year:
        query = query.filter(extract('year', RevenueEntry.date_earned) == year)
    if source_type:
        query = query.filter_by(source_type=source_type)

    # Paginated entries
    pagination = query.order_by(RevenueEntry.date_earned.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Get available years for filter
    years = db.session.query(
        extract('year', RevenueEntry.date_earned).label('year')
    ).filter(
        RevenueEntry.user_id == current_user.id
    ).distinct().order_by(extract('year', RevenueEntry.date_earned).desc()).all()
    years = [int(y[0]) for y in years if y[0]]

    # Total revenue stats
    total_revenue = db.session.query(
        func.coalesce(func.sum(RevenueEntry.amount), 0)
    ).filter(RevenueEntry.user_id == current_user.id).scalar()

    # Revenue by source type (for diversification analysis)
    revenue_by_source = db.session.query(
        RevenueEntry.source_type,
        func.sum(RevenueEntry.amount).label('total')
    ).filter(
        RevenueEntry.user_id == current_user.id
    ).group_by(RevenueEntry.source_type).order_by(
        func.sum(RevenueEntry.amount).desc()
    ).all()

    # Calculate diversification score (0-100)
    # Higher score = more diversified
    # Score based on how evenly distributed income is across sources
    diversification_score = calculate_diversification_score(revenue_by_source, total_revenue)

    # Revenue by month (for trend chart)
    monthly_revenue = db.session.query(
        extract('year', RevenueEntry.date_earned).label('year'),
        extract('month', RevenueEntry.date_earned).label('month'),
        func.sum(RevenueEntry.amount).label('total')
    ).filter(
        RevenueEntry.user_id == current_user.id
    ).group_by(
        extract('year', RevenueEntry.date_earned),
        extract('month', RevenueEntry.date_earned)
    ).order_by(
        extract('year', RevenueEntry.date_earned),
        extract('month', RevenueEntry.date_earned)
    ).all()

    # Top revenue sources (specific names, not types)
    top_sources = db.session.query(
        RevenueEntry.source_name,
        RevenueEntry.source_type,
        func.sum(RevenueEntry.amount).label('total')
    ).filter(
        RevenueEntry.user_id == current_user.id
    ).group_by(
        RevenueEntry.source_name,
        RevenueEntry.source_type
    ).order_by(
        func.sum(RevenueEntry.amount).desc()
    ).limit(10).all()

    # Risk alerts
    risk_alerts = generate_risk_alerts(revenue_by_source, total_revenue)

    # Year-to-date revenue
    current_year = datetime.now().year
    ytd_revenue = db.session.query(
        func.coalesce(func.sum(RevenueEntry.amount), 0)
    ).filter(
        RevenueEntry.user_id == current_user.id,
        extract('year', RevenueEntry.date_earned) == current_year
    ).scalar()

    # Last month revenue
    today = date.today()
    last_month = today.month - 1 if today.month > 1 else 12
    last_month_year = today.year if today.month > 1 else today.year - 1
    last_month_revenue = db.session.query(
        func.coalesce(func.sum(RevenueEntry.amount), 0)
    ).filter(
        RevenueEntry.user_id == current_user.id,
        extract('year', RevenueEntry.date_earned) == last_month_year,
        extract('month', RevenueEntry.date_earned) == last_month
    ).scalar()

    return render_template('revenue/dashboard.html',
        entries=pagination.items,
        pagination=pagination,
        years=years,
        current_year_filter=year,
        current_source_type=source_type,
        total_revenue=float(total_revenue) if total_revenue else 0,
        ytd_revenue=float(ytd_revenue) if ytd_revenue else 0,
        last_month_revenue=float(last_month_revenue) if last_month_revenue else 0,
        revenue_by_source=revenue_by_source,
        monthly_revenue=monthly_revenue,
        top_sources=top_sources,
        diversification_score=diversification_score,
        risk_alerts=risk_alerts,
        source_types=RevenueEntry.SOURCE_TYPES,
    )


def calculate_diversification_score(revenue_by_source, total_revenue):
    """Calculate diversification score (0-100).

    Uses a simplified Herfindahl-Hirschman Index approach:
    - 100 = perfectly diversified (equal distribution)
    - 0 = completely concentrated (one source)
    """
    if not revenue_by_source or not total_revenue or total_revenue == 0:
        return 0

    # Calculate market shares squared
    hhi = 0
    for source_type, amount in revenue_by_source:
        share = float(amount) / float(total_revenue)
        hhi += share ** 2

    # Convert to 0-100 scale (1/n is perfect diversification)
    n = len(revenue_by_source)
    if n <= 1:
        return 0

    # Normalize: HHI ranges from 1/n (diversified) to 1 (concentrated)
    # Score = (1 - HHI) / (1 - 1/n) * 100
    min_hhi = 1.0 / n
    if hhi <= min_hhi:
        return 100

    score = (1 - hhi) / (1 - min_hhi) * 100
    return max(0, min(100, round(score)))


def generate_risk_alerts(revenue_by_source, total_revenue):
    """Generate risk alerts based on revenue concentration."""
    alerts = []

    if not revenue_by_source or not total_revenue or total_revenue == 0:
        return alerts

    for source_type, amount in revenue_by_source:
        share = float(amount) / float(total_revenue) * 100

        if share >= 80:
            alerts.append({
                'level': 'critical',
                'message': f'{share:.0f}% of income from {source_type}. High concentration risk!',
                'source_type': source_type,
            })
        elif share >= 60:
            alerts.append({
                'level': 'warning',
                'message': f'{share:.0f}% of income from {source_type}. Consider diversifying.',
                'source_type': source_type,
            })

    return alerts


@revenue_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_entry():
    """Add a new revenue entry manually."""
    if request.method == 'POST':
        try:
            form = FormData(request.form)

            source_type = form.choice('source_type',
                [t[0] for t in RevenueEntry.SOURCE_TYPES],
                default=RevenueEntry.SOURCE_OTHER)

            source_name = form.required('source_name')
            if not source_name:
                raise ValidationError('Source Name', 'This field is required.')

            amount = form.decimal('amount')
            if amount is None or amount <= 0:
                raise ValidationError('Amount', 'Please enter a valid positive amount.')

            date_earned = form.date('date_earned')
            if not date_earned:
                raise ValidationError('Date Earned', 'This field is required.')

            entry = RevenueEntry(
                user_id=current_user.id,
                source_type=source_type,
                source_name=source_name,
                amount=amount,
                currency=form.optional('currency') or 'USD',
                date_earned=date_earned,
                date_received=form.date('date_received'),
                notes=form.optional('notes'),
            )

            db.session.add(entry)
            db.session.commit()
            flash('Revenue entry added successfully.', 'success')
            return redirect(url_for('revenue.dashboard'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('revenue/form.html',
                entry=None,
                source_types=RevenueEntry.SOURCE_TYPES)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('revenue/form.html',
                entry=None,
                source_types=RevenueEntry.SOURCE_TYPES)

    return render_template('revenue/form.html',
        entry=None,
        source_types=RevenueEntry.SOURCE_TYPES)


@revenue_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_entry(id):
    """Edit an existing revenue entry."""
    entry = RevenueEntry.query.get_or_404(id)
    if entry.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            source_type = form.choice('source_type',
                [t[0] for t in RevenueEntry.SOURCE_TYPES],
                default=RevenueEntry.SOURCE_OTHER)

            source_name = form.required('source_name')
            if not source_name:
                raise ValidationError('Source Name', 'This field is required.')

            amount = form.decimal('amount')
            if amount is None or amount <= 0:
                raise ValidationError('Amount', 'Please enter a valid positive amount.')

            date_earned = form.date('date_earned')
            if not date_earned:
                raise ValidationError('Date Earned', 'This field is required.')

            entry.source_type = source_type
            entry.source_name = source_name
            entry.amount = amount
            entry.currency = form.optional('currency') or 'USD'
            entry.date_earned = date_earned
            entry.date_received = form.date('date_received')
            entry.notes = form.optional('notes')

            db.session.commit()
            flash('Revenue entry updated successfully.', 'success')
            return redirect(url_for('revenue.dashboard'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('revenue/form.html',
                entry=entry,
                source_types=RevenueEntry.SOURCE_TYPES)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('revenue/form.html',
                entry=entry,
                source_types=RevenueEntry.SOURCE_TYPES)

    return render_template('revenue/form.html',
        entry=entry,
        source_types=RevenueEntry.SOURCE_TYPES)


@revenue_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_entry(id):
    """Delete a revenue entry."""
    try:
        entry = RevenueEntry.query.get_or_404(id)
        if entry.user_id != current_user.id:
            abort(403)

        db.session.delete(entry)
        db.session.commit()
        flash('Revenue entry deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('revenue.dashboard'))


@revenue_bp.route('/sync-affiliates', methods=['POST'])
@login_required
def sync_affiliates():
    """Sync AffiliateRevenue entries to RevenueEntry for unified view."""
    try:
        # Get all affiliate revenue entries that don't have corresponding RevenueEntry
        affiliate_entries = AffiliateRevenue.query.options(
            joinedload(AffiliateRevenue.company)
        ).filter_by(user_id=current_user.id).all()

        synced = 0
        for aff in affiliate_entries:
            # Check if already synced
            existing = RevenueEntry.query.filter_by(
                user_id=current_user.id,
                affiliate_revenue_id=aff.id
            ).first()

            if not existing:
                # Create revenue entry
                entry = RevenueEntry(
                    user_id=current_user.id,
                    source_type=RevenueEntry.SOURCE_AFFILIATE,
                    source_name=aff.company.name if aff.company else 'Unknown',
                    affiliate_revenue_id=aff.id,
                    amount=Decimal(str(aff.revenue)) if aff.revenue else Decimal('0'),
                    date_earned=date(aff.year, aff.month, 1),
                    notes=aff.notes,
                )
                db.session.add(entry)
                synced += 1

        db.session.commit()
        flash(f'Synced {synced} affiliate revenue entries.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Sync affiliates', e)
        flash('Error syncing affiliate revenue. Please try again.', 'error')

    return redirect(url_for('revenue.dashboard'))


@revenue_bp.route('/sync-sponsorships', methods=['POST'])
@login_required
def sync_sponsorships():
    """Sync completed/paid SalesPipeline deals to RevenueEntry."""
    try:
        # Get completed deals with payments that aren't already synced
        deals = SalesPipeline.query.options(
            joinedload(SalesPipeline.company)
        ).filter(
            SalesPipeline.user_id == current_user.id,
            SalesPipeline.status == 'completed',
            SalesPipeline.payment_status == 'paid',
            SalesPipeline.rate_agreed.isnot(None)
        ).all()

        synced = 0
        for deal in deals:
            # Check if already synced
            existing = RevenueEntry.query.filter_by(
                user_id=current_user.id,
                pipeline_deal_id=deal.id
            ).first()

            if not existing:
                entry = RevenueEntry(
                    user_id=current_user.id,
                    source_type=RevenueEntry.SOURCE_SPONSORSHIP,
                    source_name=deal.company.name if deal.company else 'Unknown Sponsor',
                    pipeline_deal_id=deal.id,
                    amount=Decimal(str(deal.rate_agreed)),
                    date_earned=deal.payment_date or deal.deadline or date.today(),
                    date_received=deal.payment_date,
                    notes=deal.deliverables,
                )
                db.session.add(entry)
                synced += 1

        db.session.commit()
        flash(f'Synced {synced} sponsorship deals.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Sync sponsorships', e)
        flash('Error syncing sponsorship deals. Please try again.', 'error')

    return redirect(url_for('revenue.dashboard'))


@revenue_bp.route('/export/csv')
@login_required
def export_csv():
    """Export all revenue entries as CSV for tax/accounting purposes."""
    year = request.args.get('year', type=int)

    query = RevenueEntry.query.filter_by(user_id=current_user.id)
    if year:
        query = query.filter(extract('year', RevenueEntry.date_earned) == year)

    entries = query.order_by(
        RevenueEntry.date_earned.desc()
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Date Earned', 'Date Received', 'Source Type', 'Source Name',
        'Amount', 'Currency', 'Notes'
    ])

    # Data rows
    for entry in entries:
        writer.writerow([
            entry.date_earned.isoformat() if entry.date_earned else '',
            entry.date_received.isoformat() if entry.date_received else '',
            entry.source_type,
            entry.source_name,
            f'{float(entry.amount):.2f}' if entry.amount else '0.00',
            entry.currency or 'USD',
            entry.notes or ''
        ])

    output.seek(0)
    filename = f'revenue_export_{year or "all"}.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
