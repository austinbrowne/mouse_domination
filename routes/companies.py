from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Company
from app import db

companies_bp = Blueprint('companies', __name__)


@companies_bp.route('/')
def list_companies():
    """List all companies with optional filtering."""
    category = request.args.get('category')
    status = request.args.get('status')
    priority = request.args.get('priority')
    search = request.args.get('search', '')

    query = Company.query

    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(relationship_status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if search:
        query = query.filter(Company.name.ilike(f'%{search}%'))

    companies = query.order_by(Company.name).all()

    return render_template('companies/list.html',
        companies=companies,
        current_category=category,
        current_status=status,
        current_priority=priority,
        search=search,
    )


@companies_bp.route('/new', methods=['GET', 'POST'])
def new_company():
    """Create a new company."""
    if request.method == 'POST':
        # Check for duplicate
        existing = Company.query.filter_by(name=request.form['name']).first()
        if existing:
            flash(f'Company "{request.form["name"]}" already exists.', 'error')
            return render_template('companies/form.html', company=None)

        company = Company(
            name=request.form['name'],
            category=request.form.get('category', 'mice'),
            website=request.form.get('website') or None,
            relationship_status=request.form.get('relationship_status', 'no_contact'),
            affiliate_status=request.form.get('affiliate_status', 'no'),
            affiliate_code=request.form.get('affiliate_code') or None,
            affiliate_link=request.form.get('affiliate_link') or None,
            commission_rate=float(request.form['commission_rate']) if request.form.get('commission_rate') else None,
            notes=request.form.get('notes') or None,
            priority=request.form.get('priority', 'low'),
        )

        db.session.add(company)
        db.session.commit()
        flash(f'Company "{company.name}" created successfully.', 'success')
        return redirect(url_for('companies.list_companies'))

    return render_template('companies/form.html', company=None)


@companies_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_company(id):
    """Edit an existing company."""
    company = Company.query.get_or_404(id)

    if request.method == 'POST':
        # Check for duplicate name (excluding current)
        existing = Company.query.filter(
            Company.name == request.form['name'],
            Company.id != id
        ).first()
        if existing:
            flash(f'Company "{request.form["name"]}" already exists.', 'error')
            return render_template('companies/form.html', company=company)

        company.name = request.form['name']
        company.category = request.form.get('category', 'mice')
        company.website = request.form.get('website') or None
        company.relationship_status = request.form.get('relationship_status', 'no_contact')
        company.affiliate_status = request.form.get('affiliate_status', 'no')
        company.affiliate_code = request.form.get('affiliate_code') or None
        company.affiliate_link = request.form.get('affiliate_link') or None
        company.commission_rate = float(request.form['commission_rate']) if request.form.get('commission_rate') else None
        company.notes = request.form.get('notes') or None
        company.priority = request.form.get('priority', 'low')

        db.session.commit()
        flash(f'Company "{company.name}" updated successfully.', 'success')
        return redirect(url_for('companies.list_companies'))

    return render_template('companies/form.html', company=company)


@companies_bp.route('/<int:id>/delete', methods=['POST'])
def delete_company(id):
    """Delete a company."""
    company = Company.query.get_or_404(id)
    name = company.name
    db.session.delete(company)
    db.session.commit()
    flash(f'Company "{name}" deleted.', 'success')
    return redirect(url_for('companies.list_companies'))
