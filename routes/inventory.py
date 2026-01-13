from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Inventory, Company
from app import db
from constants import (
    INVENTORY_SOURCE_TYPE_CHOICES, INVENTORY_CONDITION_CHOICES,
    MARKETPLACE_CHOICES, DEFAULT_PAGE_SIZE
)
from services.options import get_choices_for_type, get_valid_values_for_type
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.queries import get_companies_for_dropdown

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/')
@login_required
def list_inventory():
    """List all inventory with optional filtering and pagination."""
    source_type = request.args.get('source_type')
    category = request.args.get('category')
    status = request.args.get('status')
    sold = request.args.get('sold')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # Get valid values for filtering (includes custom options)
    valid_categories = get_valid_values_for_type('inventory_category')
    valid_statuses = get_valid_values_for_type('inventory_status')

    # Eager load company relationship to avoid N+1, filter by current user
    query = Inventory.query.options(joinedload(Inventory.company)).filter_by(user_id=current_user.id)

    if source_type and source_type in INVENTORY_SOURCE_TYPE_CHOICES:
        query = query.filter_by(source_type=source_type)
    if category and category in valid_categories:
        query = query.filter_by(category=category)
    if status and status in valid_statuses:
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
    companies = get_companies_for_dropdown()

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
@login_required
def new_item():
    """Create a new inventory item."""
    # Get dynamic choices for form
    category_choices = get_choices_for_type('inventory_category')
    status_choices = get_choices_for_type('inventory_status')
    valid_categories = [v for v, _ in category_choices]
    valid_statuses = [v for v, _ in status_choices]

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Handle marketplace choice validation
            marketplace = form.choice('marketplace', MARKETPLACE_CHOICES)

            item = Inventory(
                user_id=current_user.id,
                product_name=form.required('product_name'),
                company_id=form.foreign_key('company_id', Company),
                category=form.choice('category', valid_categories, default='mouse'),
                source_type=form.choice('source_type', INVENTORY_SOURCE_TYPE_CHOICES, default='review_unit'),
                cost=form.decimal('cost', allow_negative=False) or 0.0,
                on_amazon=form.boolean('on_amazon'),
                date_acquired=form.date('date_acquired'),
                deadline=form.date('deadline'),
                status=form.choice('status', valid_statuses, default='in_queue'),
                condition=form.choice('condition', INVENTORY_CONDITION_CHOICES, default='new'),
                notes=form.optional('notes'),
                short_url=form.optional('short_url'),
                short_publish_date=form.date('short_publish_date'),
                video_url=form.optional('video_url'),
                video_publish_date=form.date('video_publish_date'),
                sold=form.boolean('sold'),
                sale_price=form.decimal('sale_price', allow_negative=False),
                fees=form.decimal('fees', allow_negative=False),
                shipping=form.decimal('shipping', allow_negative=False),
                marketplace=marketplace,
                buyer=form.optional('buyer'),
                sale_notes=form.optional('sale_notes'),
            )

            db.session.add(item)
            db.session.commit()
            flash(f'Item "{item.product_name}" created successfully.', 'success')
            return redirect(url_for('inventory.list_inventory'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            return render_template('inventory/form.html', item=None, companies=companies,
                                   category_choices=category_choices, status_choices=status_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            return render_template('inventory/form.html', item=None, companies=companies,
                                   category_choices=category_choices, status_choices=status_choices)

    companies = get_companies_for_dropdown()
    return render_template('inventory/form.html', item=None, companies=companies,
                           category_choices=category_choices, status_choices=status_choices)


@inventory_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(id):
    """Edit an existing inventory item."""
    # Only allow editing own items
    item = Inventory.query.options(joinedload(Inventory.company)).filter_by(
        id=id, user_id=current_user.id
    ).first_or_404()

    # Get dynamic choices for form
    category_choices = get_choices_for_type('inventory_category')
    status_choices = get_choices_for_type('inventory_status')
    valid_categories = [v for v, _ in category_choices]
    valid_statuses = [v for v, _ in status_choices]

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Handle marketplace choice validation
            marketplace = form.choice('marketplace', MARKETPLACE_CHOICES)

            item.product_name = form.required('product_name')
            item.company_id = form.foreign_key('company_id', Company)
            item.category = form.choice('category', valid_categories, default='mouse')
            item.source_type = form.choice('source_type', INVENTORY_SOURCE_TYPE_CHOICES, default='review_unit')
            item.cost = form.decimal('cost', allow_negative=False) or 0.0
            item.on_amazon = form.boolean('on_amazon')
            item.date_acquired = form.date('date_acquired')
            item.deadline = form.date('deadline')
            item.status = form.choice('status', valid_statuses, default='in_queue')
            item.condition = form.choice('condition', INVENTORY_CONDITION_CHOICES, default='new')
            item.notes = form.optional('notes')
            item.short_url = form.optional('short_url')
            item.short_publish_date = form.date('short_publish_date')
            item.video_url = form.optional('video_url')
            item.video_publish_date = form.date('video_publish_date')
            item.sold = form.boolean('sold')
            item.sale_price = form.decimal('sale_price', allow_negative=False)
            item.fees = form.decimal('fees', allow_negative=False)
            item.shipping = form.decimal('shipping', allow_negative=False)
            item.marketplace = marketplace
            item.buyer = form.optional('buyer')
            item.sale_notes = form.optional('sale_notes')

            db.session.commit()
            flash(f'Item "{item.product_name}" updated successfully.', 'success')
            return redirect(url_for('inventory.list_inventory'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            return render_template('inventory/form.html', item=item, companies=companies,
                                   category_choices=category_choices, status_choices=status_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            return render_template('inventory/form.html', item=item, companies=companies,
                                   category_choices=category_choices, status_choices=status_choices)

    companies = get_companies_for_dropdown()
    return render_template('inventory/form.html', item=item, companies=companies,
                           category_choices=category_choices, status_choices=status_choices)


@inventory_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_item(id):
    """Delete an inventory item."""
    try:
        # Only allow deleting own items
        item = Inventory.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        name = item.product_name
        db.session.delete(item)
        db.session.commit()
        flash(f'Item "{name}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('inventory.list_inventory'))


@inventory_bp.route('/<int:id>/mark-sold', methods=['POST'])
@login_required
def mark_sold(id):
    """Quick action to mark an item as sold."""
    try:
        # Only allow marking own items as sold
        item = Inventory.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        item.sold = True
        item.status = 'sold'
        db.session.commit()
        flash(f'Item "{item.product_name}" marked as sold.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('inventory.list_inventory'))


@inventory_bp.route('/<int:id>/update-field', methods=['POST'])
@login_required
def update_field(id):
    """Inline update for a single field (source_type or status)."""
    from flask import jsonify

    try:
        # Only allow updating own items
        item = Inventory.query.filter_by(id=id, user_id=current_user.id).first_or_404()

        field = request.form.get('field')
        value = request.form.get('value')

        if field == 'source_type':
            valid_values = [v for v, _ in INVENTORY_SOURCE_TYPE_CHOICES]
            if value not in valid_values:
                return jsonify({'success': False, 'error': 'Invalid source type'}), 400
            item.source_type = value
        elif field == 'status':
            valid_statuses = get_valid_values_for_type('inventory_status')
            if value not in valid_statuses:
                return jsonify({'success': False, 'error': 'Invalid status'}), 400
            item.status = value
            # If marked as sold, also set the sold flag
            if value == 'sold':
                item.sold = True
        else:
            return jsonify({'success': False, 'error': 'Invalid field'}), 400

        db.session.commit()
        return jsonify({'success': True})

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500
