import pytest
from app import db
from models import Contact, Company, Inventory, AffiliateRevenue, User
from datetime import date


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_200(self, client):
        """Test health check endpoint returns 200 when healthy."""
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
        assert 'timestamp' in data


class TestUnauthenticatedAccess:
    """Tests that protected routes redirect to login."""

    def test_dashboard_redirects_when_not_logged_in(self, client):
        """Test dashboard redirects to login for unauthenticated users."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_contacts_redirects_when_not_logged_in(self, client):
        """Test contacts redirects to login for unauthenticated users."""
        response = client.get('/contacts/')
        assert response.status_code == 302
        assert '/auth/login' in response.location


class TestDashboard:
    """Tests for dashboard route."""

    def test_dashboard_loads(self, auth_client):
        """Test dashboard renders successfully."""
        response = auth_client.get('/')
        assert response.status_code == 200

    def test_dashboard_with_data(self, auth_client, app, test_user):
        """Test dashboard shows correct stats."""
        with app.app_context():
            # Re-query user in this context
            user = User.query.filter_by(email='test@example.com').first()

            company = Company(name='Test Co', relationship_status='active')
            db.session.add(company)
            db.session.commit()

            item = Inventory(
                product_name='Test Mouse',
                company_id=company.id,
                status='in_queue',
                user_id=user.id,
            )
            db.session.add(item)
            db.session.commit()

        response = auth_client.get('/')
        assert response.status_code == 200


class TestContactRoutes:
    """Tests for contact routes."""

    def test_list_contacts_empty(self, auth_client):
        """Test contact list with no data."""
        response = auth_client.get('/contacts/')
        assert response.status_code == 200

    def test_create_contact(self, auth_client, app):
        """Test creating a new contact."""
        response = auth_client.post('/contacts/new', data={
            'name': 'Test Person',
            'role': 'reviewer',
            'relationship_status': 'warm',
            'twitter': '@testperson',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.filter_by(name='Test Person').first()
            assert contact is not None
            assert contact.role == 'reviewer'
            assert contact.twitter == '@testperson'

    def test_create_contact_with_company(self, auth_client, app):
        """Test creating a contact linked to a company."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = auth_client.post('/contacts/new', data={
            'name': 'Pulsar Rep',
            'role': 'company_rep',
            'company_id': company_id,
            'email': 'rep@pulsar.gg',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.filter_by(name='Pulsar Rep').first()
            assert contact.company.name == 'Pulsar'

    def test_edit_contact(self, auth_client, app):
        """Test editing a contact."""
        with app.app_context():
            contact = Contact(name='Old Name', role='other')
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id

        response = auth_client.post(f'/contacts/{contact_id}/edit', data={
            'name': 'New Name',
            'role': 'reviewer',
            'relationship_status': 'active',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = db.session.get(Contact, contact_id)
            assert contact.name == 'New Name'
            assert contact.role == 'reviewer'

    def test_delete_contact(self, auth_client, app):
        """Test deleting a contact."""
        with app.app_context():
            contact = Contact(name='To Delete')
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id

        response = auth_client.post(f'/contacts/{contact_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            contact = db.session.get(Contact, contact_id)
            assert contact is None

    def test_filter_contacts_by_role(self, auth_client, app):
        """Test filtering contacts by role."""
        with app.app_context():
            db.session.add(Contact(name='Reviewer 1', role='reviewer'))
            db.session.add(Contact(name='Company Rep', role='company_rep'))
            db.session.commit()

        response = auth_client.get('/contacts/?role=reviewer')
        assert response.status_code == 200
        assert b'Reviewer 1' in response.data


class TestCompanyRoutes:
    """Tests for company routes."""

    def test_list_companies_empty(self, auth_client):
        """Test company list with no data."""
        response = auth_client.get('/companies/')
        assert response.status_code == 200

    def test_create_company(self, auth_client, app):
        """Test creating a new company."""
        response = auth_client.post('/companies/new', data={
            'name': 'Razer',
            'category': 'mice',
            'website': 'https://razer.com',
            'relationship_status': 'active',
            'affiliate_status': 'yes',
            'affiliate_code': 'DAZZ15',
            'commission_rate': '15',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            company = Company.query.filter_by(name='Razer').first()
            assert company is not None
            assert company.affiliate_code == 'DAZZ15'
            assert company.commission_rate == 15.0

    def test_create_duplicate_company_fails(self, auth_client, app):
        """Test that duplicate company names are rejected."""
        with app.app_context():
            company = Company(name='Logitech')
            db.session.add(company)
            db.session.commit()

        response = auth_client.post('/companies/new', data={
            'name': 'Logitech',
            'category': 'mice',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already exists' in response.data

    def test_edit_company(self, auth_client, app):
        """Test editing a company."""
        with app.app_context():
            company = Company(name='Test Co', affiliate_status='no')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = auth_client.post(f'/companies/{company_id}/edit', data={
            'name': 'Test Co',
            'category': 'keyboards',
            'affiliate_status': 'yes',
            'affiliate_link': 'https://test.com?ref=dazz',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            company = db.session.get(Company, company_id)
            assert company.category == 'keyboards'
            assert company.affiliate_status == 'yes'

    def test_delete_company(self, auth_client, app):
        """Test deleting a company."""
        with app.app_context():
            company = Company(name='To Delete')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = auth_client.post(f'/companies/{company_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            company = db.session.get(Company, company_id)
            assert company is None


class TestInventoryRoutes:
    """Tests for inventory routes."""

    def test_list_inventory_empty(self, auth_client):
        """Test inventory list with no data."""
        response = auth_client.get('/inventory/')
        assert response.status_code == 200

    def test_create_review_unit(self, auth_client, app, test_user):
        """Test creating a review unit."""
        response = auth_client.post('/inventory/new', data={
            'product_name': 'Pulsar X2',
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'in_queue',
            'condition': 'new',
            'date_acquired': '2025-01-09',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Pulsar X2').first()
            assert item is not None
            assert item.source_type == 'review_unit'
            assert item.cost == 0.0

    def test_create_personal_purchase(self, auth_client, app, test_user):
        """Test creating a personal purchase."""
        response = auth_client.post('/inventory/new', data={
            'product_name': 'GPX Superlight',
            'category': 'mouse',
            'source_type': 'personal_purchase',
            'cost': '149.99',
            'status': 'keeping',
            'condition': 'new',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='GPX Superlight').first()
            assert item.source_type == 'personal_purchase'
            assert item.cost == 149.99

    def test_create_item_with_company(self, auth_client, app, test_user):
        """Test creating inventory linked to company."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = auth_client.post('/inventory/new', data={
            'product_name': 'Pulsar X2',
            'company_id': company_id,
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Pulsar X2').first()
            assert item.company.name == 'Pulsar'

    def test_create_item_with_content_links(self, auth_client, app, test_user):
        """Test creating inventory with video links."""
        response = auth_client.post('/inventory/new', data={
            'product_name': 'Reviewed Mouse',
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'reviewed',
            'short_url': 'https://youtube.com/shorts/abc123',
            'short_publish_date': '2025-01-05',
            'video_url': 'https://youtube.com/watch?v=xyz789',
            'video_publish_date': '2025-01-08',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Reviewed Mouse').first()
            assert item.short_url == 'https://youtube.com/shorts/abc123'
            assert item.video_url == 'https://youtube.com/watch?v=xyz789'

    def test_create_sold_item(self, auth_client, app, test_user):
        """Test creating a sold item with P/L tracking."""
        response = auth_client.post('/inventory/new', data={
            'product_name': 'Sold Mouse',
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'sold',
            'sold': 'yes',
            'sale_price': '80',
            'fees': '10',
            'shipping': '5',
            'marketplace': 'ebay',
            'buyer': 'buyer123',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Sold Mouse').first()
            assert item.sold is True
            assert item.sale_price == 80.0
            assert item.profit_loss == 65.0  # 80 - 10 - 5

    def test_edit_item(self, auth_client, app, test_user):
        """Test editing an inventory item."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(product_name='Old Name', status='in_queue', user_id=user.id)
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = auth_client.post(f'/inventory/{item_id}/edit', data={
            'product_name': 'New Name',
            'category': 'keyboard',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'reviewing',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = db.session.get(Inventory, item_id)
            assert item.product_name == 'New Name'
            assert item.category == 'keyboard'
            assert item.status == 'reviewing'

    def test_delete_item(self, auth_client, app, test_user):
        """Test deleting an inventory item."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(product_name='To Delete', user_id=user.id)
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = auth_client.post(f'/inventory/{item_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            item = db.session.get(Inventory, item_id)
            assert item is None

    def test_mark_sold_action(self, auth_client, app, test_user):
        """Test quick mark-as-sold action."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(product_name='To Sell', status='listed', user_id=user.id)
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = auth_client.post(f'/inventory/{item_id}/mark-sold', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            item = db.session.get(Inventory, item_id)
            assert item.sold is True
            assert item.status == 'sold'

    def test_filter_by_source_type(self, auth_client, app, test_user):
        """Test filtering inventory by source type."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            db.session.add(Inventory(product_name='Review Unit', source_type='review_unit', user_id=user.id))
            db.session.add(Inventory(product_name='Personal', source_type='personal_purchase', user_id=user.id))
            db.session.commit()

        response = auth_client.get('/inventory/?source_type=review_unit')
        assert response.status_code == 200
        assert b'Review Unit' in response.data

    def test_filter_by_sold_status(self, auth_client, app, test_user):
        """Test filtering inventory by sold status."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            db.session.add(Inventory(product_name='Unsold Item', sold=False, user_id=user.id))
            db.session.add(Inventory(product_name='Sold Item', sold=True, user_id=user.id))
            db.session.commit()

        response = auth_client.get('/inventory/?sold=yes')
        assert response.status_code == 200
        assert b'Sold Item' in response.data

    def test_ajax_search_returns_partial(self, auth_client, app, test_user):
        """Test AJAX search returns partial HTML without base template."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            db.session.add(Inventory(product_name='AJAX Test Mouse', user_id=user.id))
            db.session.commit()

        response = auth_client.get('/inventory/?ajax=1')
        assert response.status_code == 200
        # Should contain table content
        assert b'AJAX Test Mouse' in response.data
        # Should NOT contain full page elements (no extends base.html)
        assert b'<!DOCTYPE html>' not in response.data
        assert b'<html' not in response.data
        # Should contain stats div for JS updates
        assert b'id="inventory-stats"' in response.data

    def test_ajax_search_with_query(self, auth_client, app, test_user):
        """Test AJAX search filters results correctly."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            db.session.add(Inventory(product_name='Pulsar X2', user_id=user.id))
            db.session.add(Inventory(product_name='Logitech GPX', user_id=user.id))
            db.session.commit()

        response = auth_client.get('/inventory/?search=Pulsar&ajax=1')
        assert response.status_code == 200
        assert b'Pulsar X2' in response.data
        assert b'Logitech GPX' not in response.data

    def test_ajax_search_with_filters(self, auth_client, app, test_user):
        """Test AJAX search works with multiple filters."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            db.session.add(Inventory(
                product_name='Review Mouse',
                source_type='review_unit',
                status='reviewing',
                user_id=user.id
            ))
            db.session.add(Inventory(
                product_name='Purchased Mouse',
                source_type='personal_purchase',
                status='keeping',
                user_id=user.id
            ))
            db.session.commit()

        response = auth_client.get('/inventory/?source_type=review_unit&status=reviewing&ajax=1')
        assert response.status_code == 200
        assert b'Review Mouse' in response.data
        assert b'Purchased Mouse' not in response.data

    def test_ajax_stats_data_attributes(self, auth_client, app, test_user):
        """Test AJAX response includes correct stats in data attributes."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            # Add items with profit/loss
            item = Inventory(
                product_name='Sold Mouse',
                sold=True,
                sale_price=100.0,
                cost=50.0,
                user_id=user.id
            )
            db.session.add(item)
            db.session.commit()

        response = auth_client.get('/inventory/?ajax=1')
        assert response.status_code == 200
        assert b'data-count="1"' in response.data
        assert b'data-profit-loss=' in response.data

    def test_quick_add_company_success(self, auth_client, app):
        """Test quick-adding a new company from inventory form."""
        response = auth_client.post('/inventory/quick-add-company', data={
            'name': 'New Quick Company',
            'category': 'mice',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['company']['name'] == 'New Quick Company'
        assert 'id' in data['company']

        with app.app_context():
            company = Company.query.filter_by(name='New Quick Company').first()
            assert company is not None
            assert company.category == 'mice'

    def test_quick_add_company_duplicate_fails(self, auth_client, app):
        """Test quick-adding a duplicate company returns error."""
        with app.app_context():
            db.session.add(Company(name='Existing Company'))
            db.session.commit()

        response = auth_client.post('/inventory/quick-add-company', data={
            'name': 'Existing Company',
            'category': 'mice',
        })
        assert response.status_code == 409
        data = response.get_json()
        assert data['success'] is False
        assert 'already exists' in data['error']

    def test_quick_add_company_empty_name_fails(self, auth_client):
        """Test quick-adding a company with empty name returns error."""
        response = auth_client.post('/inventory/quick-add-company', data={
            'name': '',
            'category': 'mice',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()

    def test_quick_add_category_success(self, auth_client, app, test_user):
        """Test quick-adding a new inventory category."""
        response = auth_client.post('/inventory/quick-add-category', data={
            'label': 'Webcam',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['category']['label'] == 'Webcam'
        assert data['category']['value'] == 'webcam'

        with app.app_context():
            from models import CustomOption
            option = CustomOption.query.filter_by(
                option_type='inventory_category',
                value='webcam'
            ).first()
            assert option is not None
            assert option.label == 'Webcam'

    def test_quick_add_category_duplicate_fails(self, auth_client, app, test_user):
        """Test quick-adding a duplicate category returns error."""
        # 'mouse' is a built-in category
        response = auth_client.post('/inventory/quick-add-category', data={
            'label': 'Mouse',
        })
        assert response.status_code == 409
        data = response.get_json()
        assert data['success'] is False
        assert 'already exists' in data['error']

    def test_quick_add_category_empty_label_fails(self, auth_client):
        """Test quick-adding a category with empty label returns error."""
        response = auth_client.post('/inventory/quick-add-category', data={
            'label': '',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()


class TestAffiliateRoutes:
    """Tests for affiliate revenue routes."""

    def test_list_revenue_empty(self, auth_client):
        """Test revenue list with no data."""
        response = auth_client.get('/affiliates/')
        assert response.status_code == 200

    def test_create_revenue_entry(self, auth_client, app):
        """Test creating a new revenue entry."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = auth_client.post('/affiliates/new', data={
            'company_id': company_id,
            'year': '2025',
            'month': '1',
            'revenue': '150.00',
            'sales_count': '12',
            'notes': 'Good month',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            entry = AffiliateRevenue.query.filter_by(company_id=company_id).first()
            assert entry is not None
            assert entry.revenue == 150.00
            assert entry.sales_count == 12
            assert entry.notes == 'Good month'

    def test_duplicate_revenue_entry_fails(self, auth_client, app):
        """Test that duplicate company/month entries are rejected."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

            # Create existing entry
            entry = AffiliateRevenue(company_id=company_id, year=2025, month=1, revenue=100)
            db.session.add(entry)
            db.session.commit()

        response = auth_client.post('/affiliates/new', data={
            'company_id': company_id,
            'year': '2025',
            'month': '1',
            'revenue': '200.00',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already exists' in response.data

    def test_edit_revenue_entry(self, auth_client, app):
        """Test editing a revenue entry."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            entry = AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=100)
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

        response = auth_client.post(f'/affiliates/{entry_id}/edit', data={
            'revenue': '250.00',
            'sales_count': '20',
            'notes': 'Updated notes',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            entry = db.session.get(AffiliateRevenue, entry_id)
            assert entry.revenue == 250.00
            assert entry.sales_count == 20
            assert entry.notes == 'Updated notes'

    def test_delete_revenue_entry(self, auth_client, app):
        """Test deleting a revenue entry."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            entry = AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=100)
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

        response = auth_client.post(f'/affiliates/{entry_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            entry = db.session.get(AffiliateRevenue, entry_id)
            assert entry is None

    def test_filter_revenue_by_year(self, auth_client, app):
        """Test filtering revenue by year."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            db.session.add(AffiliateRevenue(company_id=company.id, year=2024, month=12, revenue=100))
            db.session.add(AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=200))
            db.session.commit()

        response = auth_client.get('/affiliates/?year=2025')
        assert response.status_code == 200

    def test_filter_revenue_by_company(self, auth_client, app):
        """Test filtering revenue by company."""
        with app.app_context():
            company1 = Company(name='Pulsar', affiliate_status='yes')
            company2 = Company(name='Lethal Gaming', affiliate_status='yes')
            db.session.add_all([company1, company2])
            db.session.commit()

            db.session.add(AffiliateRevenue(company_id=company1.id, year=2025, month=1, revenue=100))
            db.session.add(AffiliateRevenue(company_id=company2.id, year=2025, month=1, revenue=50))
            db.session.commit()
            company1_id = company1.id

        response = auth_client.get(f'/affiliates/?company_id={company1_id}')
        assert response.status_code == 200

    def test_revenue_stats_calculation(self, auth_client, app):
        """Test that revenue stats are calculated correctly."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            db.session.add(AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=100))
            db.session.add(AffiliateRevenue(company_id=company.id, year=2025, month=2, revenue=150))
            db.session.commit()

        response = auth_client.get('/affiliates/')
        assert response.status_code == 200
        # Total should be $250.00
        assert b'250.00' in response.data
