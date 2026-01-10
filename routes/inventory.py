from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Inventory, Company
from app import db
from constants import (
    INVENTORY_CATEGORY_CHOICES, INVENTORY_SOURCE_TYPE_CHOICES,
    INVENTORY_STATUS_CHOICES, INVENTORY_CONDITION_CHOICES,
    MARKETPLACE_CHOICES, DEFAULT_PAGE_SIZE
)
from utils.validation import (
    parse_date, parse_float, validate_required, validate_foreign_key,
    or_none, ValidationError
)

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/')
def list_inventory():
    """List all inventory with optional filtering and pagination."""
    source_type = request.args.get('source_type')
    category = request.args.get('category')
    status = request.args.get('status')
    sold = request.args.get('sold')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # Eager load company relationship to avoid N+1
    query = Inventory.query.options(joinedload(Inventory.company))

    if source_type and source_type in INVENTORY_SOURCE_TYPE_CHOICES:
        query = query.filter_by(source_type=source_type)
    if category and category in INVENTORY_CATEGORY_CHOICES:
        query = query.filter_by(category=category)
    if status and status in INVENTORY_STATUS_CHOICES:
        query = query.filter_by(status=status)
    if sold == 'yes':
        query = query.filter_by(sold=True)
    elif sold == 'no':
        query = query.filter_by(sold=False)
    if search:
        query = query.filter(Inventory.product_name.ilike(f"%{search}%"))

    # Paginated query
    pagination = query.order_by(Inventory.date_acquired.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )
    companies = Company.query.order_by(Company.name).all()

    # Calculate totals for current page
    total_profit_loss = sum(item.profit_loss for item in pagination.items if item.sold)

    return render_template('inventory/list.html',
        items=pagination.items,
        pagination=pagination,
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
        try:
            # Validate required fields
            product_name = validate_required(request.form.get('product_name', ''), 'Product Name')

            # Validate foreign key
            company_id = validate_foreign_key(Company, request.form.get('company_id'), 'Company')

            # Validate choices using constants
            category = request.form.get('category', 'mouse')
            if category not in INVENTORY_CATEGORY_CHOICES:
                category = 'mouse'

            source_type = request.form.get('source_type', 'review_unit')
            if source_type not in INVENTORY_SOURCE_TYPE_CHOICES:
                source_type = 'review_unit'

            status = request.form.get('status', 'in_queue')
            if status not in INVENTORY_STATUS_CHOICES:
                status = 'in_queue'

            condition = request.form.get('condition', 'new')
            if condition not in INVENTORY_CONDITION_CHOICES:
                condition = 'new'

            marketplace = or_none(request.form.get('marketplace', ''))
            if marketplace and marketplace not in MARKETPLACE_CHOICES:
                marketplace = None

            # Parse numbers with validation
            cost = parse_float(request.form.get('cost', ''), 'Cost', allow_negative=False) or 0.0
            sale_price = parse_float(request.form.get('sale_price', ''), 'Sale Price', allow_negative=False)
            fees = parse_float(request.form.get('fees', ''), 'Fees', allow_negative=False)
            shipping = parse_float(request.form.get('shipping', ''), 'Shipping', allow_negative=False)

            # Parse dates with error handling
            date_acquired = parse_date(request.form.get('date_acquired', ''), 'Date Acquired')
            deadline = parse_date(request.form.get('deadline', ''), 'Deadline')
            short_publish_date = parse_date(request.form.get('short_publish_date', ''), 'Short Publish Date')
            video_publish_date = parse_date(request.form.get('video_publish_date', ''), 'Video Publish Date')

            item = Inventory(
                product_name=product_name,
                company_id=company_id,
                category=category,
                source_type=source_type,
                cost=cost,
                on_amazon=request.form.get('on_amazon') == 'yes',
                date_acquired=date_acquired,
                deadline=deadline,
                status=status,
                condition=condition,
                notes=or_none(request.form.get('notes', '')),
                short_url=or_none(request.form.get('short_url', '')),
                short_publish_date=short_publish_date,
                video_url=or_none(request.form.get('video_url', '')),
                video_publish_date=video_publish_date,
                sold=request.form.get('sold') == 'yes',
                sale_price=sale_price,
                fees=fees,
                shipping=shipping,
                marketplace=marketplace,
                buyer=or_none(request.form.get('buyer', '')),
                sale_notes=or_none(request.form.get('sale_notes', '')),
            )

            db.session.add(item)
            db.session.commit()
            flash(f'Item "{item.product_name}" created successfully.', 'success')
            return redirect(url_for('inventory.list_inventory'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('inventory/form.html', item=None, companies=companies)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('inventory/form.html', item=None, companies=companies)

    companies = Company.query.order_by(Company.name).all()
    return render_template('inventory/form.html', item=None, companies=companies)


@inventory_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_item(id):
    """Edit an existing inventory item."""
    item = Inventory.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Validate required fields
            product_name = validate_required(request.form.get('product_name', ''), 'Product Name')

            # Validate foreign key
            company_id = validate_foreign_key(Company, request.form.get('company_id'), 'Company')

            # Validate choices using constants
            category = request.form.get('category', 'mouse')
            if category not in INVENTORY_CATEGORY_CHOICES:
                category = 'mouse'

            source_type = request.form.get('source_type', 'review_unit')
            if source_type not in INVENTORY_SOURCE_TYPE_CHOICES:
                source_type = 'review_unit'

            status = request.form.get('status', 'in_queue')
            if status not in INVENTORY_STATUS_CHOICES:
                status = 'in_queue'

            condition = request.form.get('condition', 'new')
            if condition not in INVENTORY_CONDITION_CHOICES:
                condition = 'new'

            marketplace = or_none(request.form.get('marketplace', ''))
            if marketplace and marketplace not in MARKETPLACE_CHOICES:
                marketplace = None

            # Parse numbers with validation
            cost = parse_float(request.form.get('cost', ''), 'Cost', allow_negative=False) or 0.0
            sale_price = parse_float(request.form.get('sale_price', ''), 'Sale Price', allow_negative=False)
            fees = parse_float(request.form.get('fees', ''), 'Fees', allow_negative=False)
            shipping = parse_float(request.form.get('shipping', ''), 'Shipping', allow_negative=False)

            # Parse dates with error handling
            date_acquired = parse_date(request.form.get('date_acquired', ''), 'Date Acquired')
            deadline = parse_date(request.form.get('deadline', ''), 'Deadline')
            short_publish_date = parse_date(request.form.get('short_publish_date', ''), 'Short Publish Date')
            video_publish_date = parse_date(request.form.get('video_publish_date', ''), 'Video Publish Date')

            item.product_name = product_name
            item.company_id = company_id
            item.category = category
            item.source_type = source_type
            item.cost = cost
            item.on_amazon = request.form.get('on_amazon') == 'yes'
            item.date_acquired = date_acquired
            item.deadline = deadline
            item.status = status
            item.condition = condition
            item.notes = or_none(request.form.get('notes', ''))
            item.short_url = or_none(request.form.get('short_url', ''))
            item.short_publish_date = short_publish_date
            item.video_url = or_none(request.form.get('video_url', ''))
            item.video_publish_date = video_publish_date
            item.sold = request.form.get('sold') == 'yes'
            item.sale_price = sale_price
            item.fees = fees
            item.shipping = shipping
            item.marketplace = marketplace
            item.buyer = or_none(request.form.get('buyer', ''))
            item.sale_notes = or_none(request.form.get('sale_notes', ''))

            db.session.commit()
            flash(f'Item "{item.product_name}" updated successfully.', 'success')
            return redirect(url_for('inventory.list_inventory'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('inventory/form.html', item=item, companies=companies)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('inventory/form.html', item=item, companies=companies)

    companies = Company.query.order_by(Company.name).all()
    return render_template('inventory/form.html', item=item, companies=companies)


@inventory_bp.route('/<int:id>/delete', methods=['POST'])
def delete_item(id):
    """Delete an inventory item."""
    try:
        item = Inventory.query.get_or_404(id)
        name = item.product_name
        db.session.delete(item)
        db.session.commit()
        flash(f'Item "{name}" deleted.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('inventory.list_inventory'))


@inventory_bp.route('/<int:id>/mark-sold', methods=['POST'])
def mark_sold(id):
    """Quick action to mark an item as sold."""
    try:
        item = Inventory.query.get_or_404(id)
        item.sold = True
        item.status = 'sold'
        db.session.commit()
        flash(f'Item "{item.product_name}" marked as sold.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('inventory.list_inventory'))
