from flask import Blueprint, render_template, jsonify, g, current_app
from flask_login import login_required, current_user
from models import Contact, Company, Inventory, AffiliateRevenue, SalesPipeline, Collaboration
from app import db
from sqlalchemy import func, case, and_, text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)


@main_bp.route('/health')
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    try:
        # Test database connectivity
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    except SQLAlchemyError as e:
        current_app.logger.error(f'Health check failed: {e}')
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': 'Database connection failed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 500


@main_bp.route('/')
@login_required
def dashboard():
    """Main dashboard with overview metrics - optimized with database aggregations."""

    # Quick stats using single query with multiple counts (shared data)
    total_contacts = Contact.query.count()
    total_companies = Company.query.count()
    active_companies_count = Company.query.filter(
        Company.relationship_status.in_(['active', 'affiliate_only'])
    ).count()

    # Inventory stats - filtered by current user
    user_id = current_user.id
    inventory_stats = db.session.query(
        func.count(Inventory.id).label('total'),
        func.sum(case((Inventory.status == 'in_queue', 1), else_=0)).label('in_queue'),
        func.sum(case((Inventory.status == 'reviewing', 1), else_=0)).label('reviewing'),
        func.sum(case((Inventory.status == 'listed', 1), else_=0)).label('listed'),
        func.sum(case((Inventory.sold == True, 1), else_=0)).label('sold_count'),
        func.sum(case((Inventory.source_type == 'review_unit', 1), else_=0)).label('review_units'),
        func.sum(case((Inventory.source_type == 'personal_purchase', 1), else_=0)).label('personal_purchases'),
    ).filter(Inventory.user_id == user_id).first()

    # Calculate total P/L using database aggregation - filtered by user
    total_profit_loss = db.session.query(
        func.sum(
            case(
                (Inventory.sold == True,
                 func.coalesce(Inventory.sale_price, 0) -
                 func.coalesce(Inventory.fees, 0) -
                 func.coalesce(Inventory.shipping, 0) -
                 func.coalesce(Inventory.cost, 0)),
                else_=0
            )
        )
    ).filter(Inventory.user_id == user_id).scalar() or 0

    # Upcoming deadlines (next 14 days) - filtered by user
    today = datetime.now().date()
    two_weeks = today + timedelta(days=14)
    upcoming_deadlines = Inventory.query.options(
        joinedload(Inventory.company)
    ).filter(
        Inventory.user_id == user_id,
        Inventory.deadline.isnot(None),
        Inventory.deadline >= today,
        Inventory.deadline <= two_weeks,
        Inventory.status.in_(['in_queue', 'reviewing'])
    ).order_by(Inventory.deadline).limit(5).all()

    # Recent items - filtered by user
    recent_inventory = Inventory.query.options(
        joinedload(Inventory.company)
    ).filter_by(user_id=user_id).order_by(Inventory.created_at.desc()).limit(5).all()

    recent_sales = Inventory.query.options(
        joinedload(Inventory.company)
    ).filter_by(user_id=user_id, sold=True).order_by(Inventory.updated_at.desc()).limit(5).all()

    # Affiliate revenue stats - filtered by current user
    current_year = datetime.now().year

    # Single query for yearly and total affiliate revenue (user's data only)
    affiliate_stats = db.session.query(
        func.coalesce(func.sum(case((AffiliateRevenue.year == current_year, AffiliateRevenue.revenue), else_=0)), 0).label('yearly'),
        func.coalesce(func.sum(AffiliateRevenue.revenue), 0).label('total')
    ).filter(AffiliateRevenue.user_id == user_id).first()

    yearly_affiliate_revenue = affiliate_stats.yearly
    total_affiliate_revenue = affiliate_stats.total

    # Monthly affiliate revenue for chart - single query with GROUP BY (user's data only)
    current_month = datetime.now().month
    monthly_data = db.session.query(
        AffiliateRevenue.year,
        AffiliateRevenue.month,
        func.sum(AffiliateRevenue.revenue).label('total')
    ).filter(
        AffiliateRevenue.user_id == user_id,
        # Last 12 months
        ((AffiliateRevenue.year == current_year) |
         ((AffiliateRevenue.year == current_year - 1) & (AffiliateRevenue.month > current_month)))
    ).group_by(
        AffiliateRevenue.year,
        AffiliateRevenue.month
    ).all()

    # Build lookup dict
    revenue_lookup = {(row.year, row.month): float(row.total) for row in monthly_data}

    # Generate last 12 months labels and values
    monthly_revenue = []
    for i in range(11, -1, -1):
        target_date = datetime.now() - timedelta(days=i*30)
        month = target_date.month
        year = target_date.year
        revenue = revenue_lookup.get((year, month), 0)
        month_name = target_date.strftime('%b')
        monthly_revenue.append({'month': f"{month_name} {year}", 'revenue': revenue})

    # Total revenue from all sources
    total_revenue = total_affiliate_revenue + total_profit_loss

    # Pipeline conversion funnel (user's data only)
    pipeline_funnel = db.session.query(
        func.sum(case((SalesPipeline.status == 'lead', 1), else_=0)).label('leads'),
        func.sum(case((SalesPipeline.status == 'negotiating', 1), else_=0)).label('negotiating'),
        func.sum(case((SalesPipeline.status == 'confirmed', 1), else_=0)).label('confirmed'),
        func.sum(case((SalesPipeline.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(case((SalesPipeline.status == 'lost', 1), else_=0)).label('lost'),
    ).filter(SalesPipeline.user_id == user_id).first()

    funnel = {
        'leads': int(pipeline_funnel.leads or 0),
        'negotiating': int(pipeline_funnel.negotiating or 0),
        'confirmed': int(pipeline_funnel.confirmed or 0),
        'completed': int(pipeline_funnel.completed or 0),
        'lost': int(pipeline_funnel.lost or 0),
    }
    # Calculate conversion rate
    total_leads = funnel['leads'] + funnel['negotiating'] + funnel['confirmed'] + funnel['completed'] + funnel['lost']
    funnel['conversion_rate'] = (funnel['completed'] / total_leads * 100) if total_leads > 0 else 0

    # Collaboration stats (user's data only)
    collab_stats = db.session.query(
        func.count(Collaboration.id).label('total'),
        func.sum(case((Collaboration.status == 'confirmed', 1), else_=0)).label('confirmed'),
        func.sum(case((Collaboration.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(case((Collaboration.follow_up_needed == True, 1), else_=0)).label('needs_follow_up'),
    ).filter(Collaboration.user_id == user_id).first()

    return render_template('dashboard.html',
        total_contacts=total_contacts,
        total_companies=total_companies,
        active_companies=active_companies_count,
        total_inventory=inventory_stats.total or 0,
        in_queue=inventory_stats.in_queue or 0,
        reviewing=inventory_stats.reviewing or 0,
        listed=inventory_stats.listed or 0,
        sold_count=inventory_stats.sold_count or 0,
        review_units=inventory_stats.review_units or 0,
        personal_purchases=inventory_stats.personal_purchases or 0,
        total_profit_loss=total_profit_loss,
        upcoming_deadlines=upcoming_deadlines,
        recent_inventory=recent_inventory,
        recent_sales=recent_sales,
        yearly_affiliate_revenue=yearly_affiliate_revenue,
        total_affiliate_revenue=total_affiliate_revenue,
        total_revenue=total_revenue,
        monthly_revenue=monthly_revenue,  # Use tojson filter in template for XSS safety
        current_year=current_year,
        # Pipeline funnel
        pipeline_funnel=funnel,
        # Collaboration stats
        collab_total=collab_stats.total or 0,
        collab_confirmed=collab_stats.confirmed or 0,
        collab_completed=collab_stats.completed or 0,
        collab_needs_follow_up=collab_stats.needs_follow_up or 0,
    )
