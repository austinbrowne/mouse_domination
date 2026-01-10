from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Inventory, Company
from app import db
from datetime import datetime

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/')
def list_inventory():
    """List all inventory with optional filtering."""
    source_type = request.args.get('source_type')
    category = request.args.get('category')
    status = request.args.get('status')
    sold = request.args.get('sold')
    search = request.args.get('search', '')

    query = Inventory.query

    if source_type:
        query = query.filter_by(source_type=source_type)
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    if sold == 'yes':
        query = query.filter_by(sold=True)
    elif sold == 'no':
        query = query.filter_by(sold=False)
    if search:
        query = query.filter(Inventory.product_name.ilike(f'%{search}%'))

    items = query.order_by(Inventory.date_acquired.desc()).all()
    companies = Company.query.order_by(Company.name).all()

    # Calculate totals
    total_profit_loss = sum(item.profit_loss for item in items if item.sold)

    return render_template('inventory/list.html',
        items=items,
        companies=companies,
        current_source_type=source_type,
        current_category=category,
        current_status=status,
        current_sold=sold,
        search=search,
        total_profit_loss=total_profit_loss,
    )


@inventory_bp.route('/new', methods=['GET', 'POST'])
def new_item():
    """Create a new inventory item."""
    if request.method == 'POST':
        item = Inventory(
            product_name=request.form['product_name'],
            company_id=request.form.get('company_id') or None,
            category=request.form.get('category', 'mouse'),
            source_type=request.form.get('source_type', 'review_unit'),
            cost=float(request.form['cost']) if request.form.get('cost') else 0.0,
            on_amazon=request.form.get('on_amazon') == 'yes',
            status=request.form.get('status', 'in_queue'),
            condition=request.form.get('condition', 'new'),
            notes=request.form.get('notes') or None,
            short_url=request.form.get('short_url') or None,
            video_url=request.form.get('video_url') or None,
            sold=request.form.get('sold') == 'yes',
            sale_price=float(request.form['sale_price']) if request.form.get('sale_price') else None,
            fees=float(request.form['fees']) if request.form.get('fees') else None,
            shipping=float(request.form['shipping']) if request.form.get('shipping') else None,
            marketplace=request.form.get('marketplace') or None,
            buyer=request.form.get('buyer') or None,
            sale_notes=request.form.get('sale_notes') or None,
        )

        # Parse dates
        if request.form.get('date_acquired'):
            item.date_acquired = datetime.strptime(request.form['date_acquired'], '%Y-%m-%d').date()
        if request.form.get('deadline'):
            item.deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%d').date()
        if request.form.get('short_publish_date'):
            item.short_publish_date = datetime.strptime(request.form['short_publish_date'], '%Y-%m-%d').date()
        if request.form.get('video_publish_date'):
            item.video_publish_date = datetime.strptime(request.form['video_publish_date'], '%Y-%m-%d').date()

        db.session.add(item)
        db.session.commit()
        flash(f'Item "{item.product_name}" created successfully.', 'success')
        return redirect(url_for('inventory.list_inventory'))

    companies = Company.query.order_by(Company.name).all()
    return render_template('inventory/form.html', item=None, companies=companies)


@inventory_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_item(id):
    """Edit an existing inventory item."""
    item = Inventory.query.get_or_404(id)

    if request.method == 'POST':
        item.product_name = request.form['product_name']
        item.company_id = request.form.get('company_id') or None
        item.category = request.form.get('category', 'mouse')
        item.source_type = request.form.get('source_type', 'review_unit')
        item.cost = float(request.form['cost']) if request.form.get('cost') else 0.0
        item.on_amazon = request.form.get('on_amazon') == 'yes'
        item.status = request.form.get('status', 'in_queue')
        item.condition = request.form.get('condition', 'new')
        item.notes = request.form.get('notes') or None
        item.short_url = request.form.get('short_url') or None
        item.video_url = request.form.get('video_url') or None
        item.sold = request.form.get('sold') == 'yes'
        item.sale_price = float(request.form['sale_price']) if request.form.get('sale_price') else None
        item.fees = float(request.form['fees']) if request.form.get('fees') else None
        item.shipping = float(request.form['shipping']) if request.form.get('shipping') else None
        item.marketplace = request.form.get('marketplace') or None
        item.buyer = request.form.get('buyer') or None
        item.sale_notes = request.form.get('sale_notes') or None

        # Parse dates
        item.date_acquired = datetime.strptime(request.form['date_acquired'], '%Y-%m-%d').date() if request.form.get('date_acquired') else None
        item.deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%d').date() if request.form.get('deadline') else None
        item.short_publish_date = datetime.strptime(request.form['short_publish_date'], '%Y-%m-%d').date() if request.form.get('short_publish_date') else None
        item.video_publish_date = datetime.strptime(request.form['video_publish_date'], '%Y-%m-%d').date() if request.form.get('video_publish_date') else None

        db.session.commit()
        flash(f'Item "{item.product_name}" updated successfully.', 'success')
        return redirect(url_for('inventory.list_inventory'))

    companies = Company.query.order_by(Company.name).all()
    return render_template('inventory/form.html', item=item, companies=companies)


@inventory_bp.route('/<int:id>/delete', methods=['POST'])
def delete_item(id):
    """Delete an inventory item."""
    item = Inventory.query.get_or_404(id)
    name = item.product_name
    db.session.delete(item)
    db.session.commit()
    flash(f'Item "{name}" deleted.', 'success')
    return redirect(url_for('inventory.list_inventory'))


@inventory_bp.route('/<int:id>/mark-sold', methods=['POST'])
def mark_sold(id):
    """Quick action to mark an item as sold."""
    item = Inventory.query.get_or_404(id)
    item.sold = True
    item.status = 'sold'
    db.session.commit()
    flash(f'Item "{item.product_name}" marked as sold.', 'success')
    return redirect(url_for('inventory.list_inventory'))
