from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Contact, Company
from app import db
from datetime import datetime

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/')
def list_contacts():
    """List all contacts with optional filtering."""
    role = request.args.get('role')
    status = request.args.get('status')
    search = request.args.get('search', '')

    query = Contact.query

    if role:
        query = query.filter_by(role=role)
    if status:
        query = query.filter_by(relationship_status=status)
    if search:
        query = query.filter(Contact.name.ilike(f'%{search}%'))

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
        contact = Contact(
            name=request.form['name'],
            role=request.form.get('role', 'other'),
            company_id=request.form.get('company_id') or None,
            email=request.form.get('email') or None,
            twitter=request.form.get('twitter') or None,
            discord=request.form.get('discord') or None,
            youtube=request.form.get('youtube') or None,
            relationship_status=request.form.get('relationship_status', 'cold'),
            notes=request.form.get('notes') or None,
            tags=request.form.get('tags') or None,
        )

        last_contact = request.form.get('last_contact_date')
        if last_contact:
            contact.last_contact_date = datetime.strptime(last_contact, '%Y-%m-%d').date()

        db.session.add(contact)
        db.session.commit()
        flash(f'Contact "{contact.name}" created successfully.', 'success')
        return redirect(url_for('contacts.list_contacts'))

    companies = Company.query.order_by(Company.name).all()
    return render_template('contacts/form.html', contact=None, companies=companies)


@contacts_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_contact(id):
    """Edit an existing contact."""
    contact = Contact.query.get_or_404(id)

    if request.method == 'POST':
        contact.name = request.form['name']
        contact.role = request.form.get('role', 'other')
        contact.company_id = request.form.get('company_id') or None
        contact.email = request.form.get('email') or None
        contact.twitter = request.form.get('twitter') or None
        contact.discord = request.form.get('discord') or None
        contact.youtube = request.form.get('youtube') or None
        contact.relationship_status = request.form.get('relationship_status', 'cold')
        contact.notes = request.form.get('notes') or None
        contact.tags = request.form.get('tags') or None

        last_contact = request.form.get('last_contact_date')
        contact.last_contact_date = datetime.strptime(last_contact, '%Y-%m-%d').date() if last_contact else None

        db.session.commit()
        flash(f'Contact "{contact.name}" updated successfully.', 'success')
        return redirect(url_for('contacts.list_contacts'))

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
