from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Contact, Company
from app import db
from constants import CONTACT_STATUS_CHOICES, DEFAULT_PAGE_SIZE
from services.options import get_choices_for_type, get_valid_values_for_type
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.queries import get_companies_for_dropdown

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/')
@login_required
def list_contacts():
    """List all contacts with optional filtering and pagination."""
    role = request.args.get('role')
    status = request.args.get('status')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # Get valid values for filtering (includes custom options)
    valid_roles = get_valid_values_for_type('contact_role')

    # Eager load company relationship to avoid N+1
    query = Contact.query.options(joinedload(Contact.company))

    if role and role in valid_roles:
        query = query.filter_by(role=role)
    if status and status in CONTACT_STATUS_CHOICES:
        query = query.filter_by(relationship_status=status)
    if search:
        query = query.filter(Contact.name.ilike(f"%{search}%"))

    # Paginated query
    pagination = query.order_by(Contact.name).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )
    companies = get_companies_for_dropdown()

    return render_template('contacts/list.html',
        contacts=pagination.items,
        pagination=pagination,
        companies=companies,
        current_role=role,
        current_status=status,
        search=search,
    )


@contacts_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_contact():
    """Create a new contact."""
    # Get dynamic choices for form
    role_choices = get_choices_for_type('contact_role')
    valid_roles = [v for v, _ in role_choices]

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            contact = Contact(
                name=form.required('name'),
                role=form.choice('role', valid_roles, default='other'),
                company_id=form.foreign_key('company_id', Company),
                email=form.email('email'),
                twitter=form.optional('twitter'),
                discord=form.optional('discord'),
                youtube=form.optional('youtube'),
                relationship_status=form.choice('relationship_status', CONTACT_STATUS_CHOICES, default='cold'),
                notes=form.optional('notes'),
                tags=form.optional('tags'),
                last_contact_date=form.date('last_contact_date'),
            )

            db.session.add(contact)
            db.session.commit()
            flash(f'Contact "{contact.name}" created successfully.', 'success')
            return redirect(url_for('contacts.list_contacts'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            return render_template('contacts/form.html', contact=None, companies=companies,
                                   role_choices=role_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Create contact', e)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            return render_template('contacts/form.html', contact=None, companies=companies,
                                   role_choices=role_choices)

    companies = get_companies_for_dropdown()
    return render_template('contacts/form.html', contact=None, companies=companies,
                           role_choices=role_choices)


@contacts_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contact(id):
    """Edit an existing contact."""
    contact = Contact.query.options(joinedload(Contact.company)).get_or_404(id)

    # Get dynamic choices for form
    role_choices = get_choices_for_type('contact_role')
    valid_roles = [v for v, _ in role_choices]

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            contact.name = form.required('name')
            contact.role = form.choice('role', valid_roles, default='other')
            contact.company_id = form.foreign_key('company_id', Company)
            contact.email = form.email('email')
            contact.twitter = form.optional('twitter')
            contact.discord = form.optional('discord')
            contact.youtube = form.optional('youtube')
            contact.relationship_status = form.choice('relationship_status', CONTACT_STATUS_CHOICES, default='cold')
            contact.notes = form.optional('notes')
            contact.tags = form.optional('tags')
            contact.last_contact_date = form.date('last_contact_date')

            db.session.commit()
            flash(f'Contact "{contact.name}" updated successfully.', 'success')
            return redirect(url_for('contacts.list_contacts'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = get_companies_for_dropdown()
            return render_template('contacts/form.html', contact=contact, companies=companies,
                                   role_choices=role_choices)
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Update contact', e, contact_id=id)
            flash('Database error occurred. Please try again.', 'error')
            companies = get_companies_for_dropdown()
            return render_template('contacts/form.html', contact=contact, companies=companies,
                                   role_choices=role_choices)

    companies = get_companies_for_dropdown()
    return render_template('contacts/form.html', contact=contact, companies=companies,
                           role_choices=role_choices)


@contacts_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_contact(id):
    """Delete a contact."""
    try:
        contact = Contact.query.get_or_404(id)
        name = contact.name
        db.session.delete(contact)
        db.session.commit()
        flash(f'Contact "{name}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete contact', e, contact_id=id)
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('contacts.list_contacts'))
