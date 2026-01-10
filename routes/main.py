from flask import Blueprint, render_template
from models import Contact, Company, Inventory
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def dashboard():
    """Main dashboard with overview metrics."""
    # Quick stats
    total_contacts = Contact.query.count()
    total_companies = Company.query.count()
    active_companies = Company.query.filter(
        Company.relationship_status.in_(['active', 'affiliate_only'])
    ).count()

    # Inventory stats
    total_inventory = Inventory.query.count()
    in_queue = Inventory.query.filter_by(status='in_queue').count()
    reviewing = Inventory.query.filter_by(status='reviewing').count()
    listed = Inventory.query.filter_by(status='listed').count()
    sold_count = Inventory.query.filter_by(sold=True).count()

    # Review units vs personal
    review_units = Inventory.query.filter_by(source_type='review_unit').count()
    personal_purchases = Inventory.query.filter_by(source_type='personal_purchase').count()

    # Calculate total P/L
    sold_items = Inventory.query.filter_by(sold=True).all()
    total_profit_loss = sum(item.profit_loss for item in sold_items)

    # Upcoming deadlines (next 14 days)
    today = datetime.now().date()
    two_weeks = today + timedelta(days=14)
    upcoming_deadlines = Inventory.query.filter(
        Inventory.deadline.isnot(None),
        Inventory.deadline >= today,
        Inventory.deadline <= two_weeks,
        Inventory.status.in_(['in_queue', 'reviewing'])
    ).order_by(Inventory.deadline).limit(5).all()

    # Recent items
    recent_inventory = Inventory.query.order_by(
        Inventory.created_at.desc()
    ).limit(5).all()

    recent_sales = Inventory.query.filter_by(sold=True).order_by(
        Inventory.updated_at.desc()
    ).limit(5).all()

    return render_template('dashboard.html',
        total_contacts=total_contacts,
        total_companies=total_companies,
        active_companies=active_companies,
        total_inventory=total_inventory,
        in_queue=in_queue,
        reviewing=reviewing,
        listed=listed,
        sold_count=sold_count,
        review_units=review_units,
        personal_purchases=personal_purchases,
        total_profit_loss=total_profit_loss,
        upcoming_deadlines=upcoming_deadlines,
        recent_inventory=recent_inventory,
        recent_sales=recent_sales,
    )
