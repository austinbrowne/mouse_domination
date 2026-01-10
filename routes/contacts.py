from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import Contact, Company
from app import db
from constants import CONTACT_ROLE_CHOICES, CONTACT_STATUS_CHOICES, DEFAULT_PAGE_SIZE
from utils.validation import (
    parse_date, validate_required, validate_email, validate_foreign_key,
    validate_choice, or_none, ValidationError
)

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/')
def list_contacts():
    """List all contacts with optional filtering and pagination."""
    role = request.args.get('role')
    status = request.args.get('status')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # Eager load company relationship to avoid N+1
    query = Contact.query.options(joinedload(Contact.company))

    if role and role in CONTACT_ROLE_CHOICES:
        query = query.filter_by(role=role)
    if status and status in CONTACT_STATUS_CHOICES:
        query = query.filter_by(relationship_status=status)
    if search:
        query = query.filter(Contact.name.ilike(f"%{search}%"))

    # Paginated query
    pagination = query.order_by(Contact.name).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )
    companies = Company.query.order_by(Company.name).all()

    return render_template('contacts/list.html',
        contacts=pagination.items,
        pagination=pagination,
        companies=companies,
        current_role=role,
        current_status=status,
        search=search,
    )


@contacts_bp.route('/new', methods=['GET', 'POST'])
def new_contact():
    """Create a new contact."""
    if request.method == 'POST':
        try:
            # Validate required fields
            name = validate_required(request.form.get('name', ''), 'Name')

            # Validate choices using constants
            role = request.form.get('role', 'other')
            if role not in CONTACT_ROLE_CHOICES:
                role = 'other'

            status = request.form.get('relationship_status', 'cold')
            if status not in CONTACT_STATUS_CHOICES:
                status = 'cold'

            # Validate foreign key
            company_id = validate_foreign_key(Company, request.form.get('company_id'), 'Company')

            # Validate email format
            email = validate_email(request.form.get('email', ''), 'Email')

            # Parse date with error handling
            last_contact_date = parse_date(request.form.get('last_contact_date', ''), 'Last Contact Date')

            contact = Contact(
                name=name,
                role=role,
                company_id=company_id,
                email=email,
                twitter=or_none(request.form.get('twitter', '')),
                discord=or_none(request.form.get('discord', '')),
                youtube=or_none(request.form.get('youtube', '')),
                relationship_status=status,
                notes=or_none(request.form.get('notes', '')),
                tags=or_none(request.form.get('tags', '')),
                last_contact_date=last_contact_date,
            )

            db.session.add(contact)
            db.session.commit()
            flash(f'Contact "{contact.name}" created successfully.', 'success')
            return redirect(url_for('contacts.list_contacts'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('contacts/form.html', contact=None, companies=companies)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('contacts/form.html', contact=None, companies=companies)

    companies = Company.query.order_by(Company.name).all()
    return render_template('contacts/form.html', contact=None, companies=companies)


@contacts_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_contact(id):
    """Edit an existing contact."""
    contact = Contact.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Validate required fields
            name = validate_required(request.form.get('name', ''), 'Name')

            # Validate choices using constants
            role = request.form.get('role', 'other')
            if role not in CONTACT_ROLE_CHOICES:
                role = 'other'

            status = request.form.get('relationship_status', 'cold')
            if status not in CONTACT_STATUS_CHOICES:
                status = 'cold'

            # Validate foreign key
            company_id = validate_foreign_key(Company, request.form.get('company_id'), 'Company')

            # Validate email format
            email = validate_email(request.form.get('email', ''), 'Email')

            # Parse date with error handling
            last_contact_date = parse_date(request.form.get('last_contact_date', ''), 'Last Contact Date')

            contact.name = name
            contact.role = role
            contact.company_id = company_id
            contact.email = email
            contact.twitter = or_none(request.form.get('twitter', ''))
            contact.discord = or_none(request.form.get('discord', ''))
            contact.youtube = or_none(request.form.get('youtube', ''))
            contact.relationship_status = status
            contact.notes = or_none(request.form.get('notes', ''))
            contact.tags = or_none(request.form.get('tags', ''))
            contact.last_contact_date = last_contact_date

            db.session.commit()
            flash(f'Contact "{contact.name}" updated successfully.', 'success')
            return redirect(url_for('contacts.list_contacts'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('contacts/form.html', contact=contact, companies=companies)
        except SQLAlchemyError:
            db.session.rollback()
            flash('Database error occurred. Please try again.', 'error')
            companies = Company.query.order_by(Company.name).all()
            return render_template('contacts/form.html', contact=contact, companies=companies)

    companies = Company.query.order_by(Company.name).all()
    return render_template('contacts/form.html', contact=contact, companies=companies)


@contacts_bp.route('/<int:id>/delete', methods=['POST'])
def delete_contact(id):
    """Delete a contact."""
    try:
        contact = Contact.query.get_or_404(id)
        name = contact.name
        db.session.delete(contact)
        db.session.commit()
        flash(f'Contact "{name}" deleted.', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Database error occurred. Please try again.', 'error')
    return redirect(url_for('contacts.list_contacts'))
