from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from markupsafe import escape
from sqlalchemy.exc import SQLAlchemyError
from models import OutreachTemplate, Contact, Company
from app import db
from constants import TEMPLATE_CATEGORY_CHOICES, DEFAULT_PAGE_SIZE
from utils.validation import validate_required, or_none, ValidationError
from utils.logging import log_exception

templates_bp = Blueprint('templates', __name__)


@templates_bp.route('/')
def list_templates():
    """List all outreach templates with optional filtering."""
    category = request.args.get('category')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = OutreachTemplate.query

    if category and category in TEMPLATE_CATEGORY_CHOICES:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(OutreachTemplate.name.ilike(f"%{search}%"))

    # Paginated query
    pagination = query.order_by(OutreachTemplate.name).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    return render_template('outreach/list.html',
        templates=pagination.items,
        pagination=pagination,
        current_category=category,
        search=search,
    )


@templates_bp.route('/new', methods=['GET', 'POST'])
def new_template():
    """Create a new outreach template."""
    if request.method == 'POST':
        try:
            name = validate_required(request.form.get('name', ''), 'Template Name')
            body = validate_required(request.form.get('body', ''), 'Body')

            # Validate category
            category = request.form.get('category', 'other')
            if category not in TEMPLATE_CATEGORY_CHOICES:
                category = 'other'

            template = OutreachTemplate(
                name=name,
                category=category,
                subject=or_none(request.form.get('subject', '')),
                body=body,
                notes=or_none(request.form.get('notes', '')),
            )

            db.session.add(template)
            db.session.commit()
            flash(f'Template "{template.name}" created successfully.', 'success')
            return redirect(url_for('templates.list_templates'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('outreach/form.html', template=None)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('outreach/form.html', template=None)

    return render_template('outreach/form.html', template=None)


@templates_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_template(id):
    """Edit an existing outreach template."""
    template = OutreachTemplate.query.get_or_404(id)

    if request.method == 'POST':
        try:
            name = validate_required(request.form.get('name', ''), 'Template Name')
            body = validate_required(request.form.get('body', ''), 'Body')

            # Validate category
            category = request.form.get('category', 'other')
            if category not in TEMPLATE_CATEGORY_CHOICES:
                category = 'other'

            template.name = name
            template.category = category
            template.subject = or_none(request.form.get('subject', ''))
            template.body = body
            template.notes = or_none(request.form.get('notes', ''))

            db.session.commit()
            flash(f'Template "{template.name}" updated successfully.', 'success')
            return redirect(url_for('templates.list_templates'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            return render_template('outreach/form.html', template=template)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Database operation', e)
            flash('Database error occurred. Please try again.', 'error')
            return render_template('outreach/form.html', template=template)

    return render_template('outreach/form.html', template=template)


@templates_bp.route('/<int:id>/delete', methods=['POST'])
def delete_template(id):
    """Delete a template."""
    try:
        template = OutreachTemplate.query.get_or_404(id)
        name = template.name
        db.session.delete(template)
        db.session.commit()
        flash(f'Template "{name}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('templates.list_templates'))


@templates_bp.route('/<int:id>/preview')
def preview_template(id):
    """Preview a template with optional placeholder data."""
    template = OutreachTemplate.query.get_or_404(id)

    # Get optional parameters for filling placeholders
    contact_id = request.args.get('contact_id', type=int)
    company_id = request.args.get('company_id', type=int)

    body = template.body
    subject = template.subject or ''

    # Replace placeholders if data provided (escape user data to prevent XSS)
    if contact_id:
        contact = Contact.query.get(contact_id)
        if contact:
            safe_name = str(escape(contact.name))
            body = body.replace('{{contact_name}}', safe_name)
            subject = subject.replace('{{contact_name}}', safe_name)

    if company_id:
        company = Company.query.get(company_id)
        if company:
            safe_name = str(escape(company.name))
            body = body.replace('{{company_name}}', safe_name)
            subject = subject.replace('{{company_name}}', safe_name)

    # Default placeholders for channel info from config
    channel_name = current_app.config.get('CREATOR_CHANNEL_NAME', 'dazztrazak')
    channel_stats = current_app.config.get('CREATOR_CHANNEL_STATS', '4,000+ subscribers')
    body = body.replace('{{my_channel}}', channel_name)
    body = body.replace('{{my_stats}}', channel_stats)
    subject = subject.replace('{{my_channel}}', channel_name)

    # Get all contacts and companies for the test form
    contacts = Contact.query.order_by(Contact.name).all()
    companies = Company.query.order_by(Company.name).all()

    return render_template('outreach/preview.html',
        template=template,
        subject=subject,
        body=body,
        contacts=contacts,
        companies=companies,
    )


@templates_bp.route('/<int:id>/use', methods=['POST'])
def use_template(id):
    """Increment usage counter for a template."""
    try:
        template = OutreachTemplate.query.get_or_404(id)
        template.times_used = (template.times_used or 0) + 1
        db.session.commit()
        return jsonify({'success': True, 'times_used': template.times_used})
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


@templates_bp.route('/<int:id>/copy', methods=['POST'])
def copy_template(id):
    """Create a copy of an existing template."""
    try:
        original = OutreachTemplate.query.get_or_404(id)

        copy = OutreachTemplate(
            name=f"{original.name} (Copy)",
            category=original.category,
            subject=original.subject,
            body=original.body,
            notes=original.notes,
        )

        db.session.add(copy)
        db.session.commit()
        flash(f'Template copied as "{copy.name}".', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Database operation', e)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('templates.list_templates'))
