from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Contact, Company
from app import db
from utils.validation import (
    parse_date, validate_required, validate_email, validate_foreign_key,
    validate_choice, or_none, ValidationError
)

contacts_bp = Blueprint('contacts', __name__)

ROLE_CHOICES = ['reviewer', 'company_rep', 'podcast_guest', 'other']
STATUS_CHOICES = ['cold', 'warm', 'active', 'close']


@contacts_bp.route('/')
def list_contacts():
    """List all contacts with optional filtering."""
    role = request.args.get('role')
    status = request.args.get('status')
    search = request.args.get('search', '').strip()

    query = Contact.query

    if role and role in ROLE_CHOICES:
        query = query.filter_by(role=role)
    if status and status in STATUS_CHOICES:
        query = query.filter_by(relationship_status=status)
    if search:
        # Use parameterized query to avoid SQL injection
        query = query.filter(Contact.name.ilike('%' + search + '%'))

    contacts = query.order_by(Contact.name).all()
    companies = Company.query.order_by(Company.name).all()

    return render_template('contacts/list.html',
        contacts=contacts,
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

            # Validate choices
            role = request.form.get('role', 'other')
            if role not in ROLE_CHOICES:
                role = 'other'

            status = request.form.get('relationship_status', 'cold')
            if status not in STATUS_CHOICES:
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

            # Validate choices
            role = request.form.get('role', 'other')
            if role not in ROLE_CHOICES:
                role = 'other'

            status = request.form.get('relationship_status', 'cold')
            if status not in STATUS_CHOICES:
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

    companies = Company.query.order_by(Company.name).all()
    return render_template('contacts/form.html', contact=contact, companies=companies)


@contacts_bp.route('/<int:id>/delete', methods=['POST'])
def delete_contact(id):
    """Delete a contact."""
    contact = Contact.query.get_or_404(id)
    name = contact.name
    db.session.delete(contact)
    db.session.commit()
    flash(f'Contact "{name}" deleted.', 'success')
    return redirect(url_for('contacts.list_contacts'))
