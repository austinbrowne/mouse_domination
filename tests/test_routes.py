import pytest
from app import db
from models import Contact, Company, Inventory


class TestDashboard:
    """Tests for dashboard route."""

    def test_dashboard_loads(self, client):
        """Test dashboard renders successfully."""
        response = client.get('/')
        assert response.status_code == 200

    def test_dashboard_with_data(self, client, app):
        """Test dashboard shows correct stats."""
        with app.app_context():
            # Add some test data
            company = Company(name='Test Co', relationship_status='active')
            db.session.add(company)
            db.session.commit()

            item = Inventory(
                product_name='Test Mouse',
                company_id=company.id,
                status='in_queue',
            )
            db.session.add(item)
            db.session.commit()

        response = client.get('/')
        assert response.status_code == 200
        assert b'Test Mouse' in response.data or b'1' in response.data  # Shows count or item


class TestContactRoutes:
    """Tests for contact routes."""

    def test_list_contacts_empty(self, client):
        """Test contact list with no data."""
        response = client.get('/contacts/')
        assert response.status_code == 200

    def test_create_contact(self, client, app):
        """Test creating a new contact."""
        response = client.post('/contacts/new', data={
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

    def test_create_contact_with_company(self, client, app):
        """Test creating a contact linked to a company."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post('/contacts/new', data={
            'name': 'Pulsar Rep',
            'role': 'company_rep',
            'company_id': company_id,
            'email': 'rep@pulsar.gg',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.filter_by(name='Pulsar Rep').first()
            assert contact.company.name == 'Pulsar'

    def test_edit_contact(self, client, app):
        """Test editing a contact."""
        with app.app_context():
            contact = Contact(name='Old Name', role='other')
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id

        response = client.post(f'/contacts/{contact_id}/edit', data={
            'name': 'New Name',
            'role': 'reviewer',
            'relationship_status': 'active',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.get(contact_id)
            assert contact.name == 'New Name'
            assert contact.role == 'reviewer'

    def test_delete_contact(self, client, app):
        """Test deleting a contact."""
        with app.app_context():
            contact = Contact(name='To Delete')
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id

        response = client.post(f'/contacts/{contact_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.get(contact_id)
            assert contact is None

    def test_filter_contacts_by_role(self, client, app):
        """Test filtering contacts by role."""
        with app.app_context():
            db.session.add(Contact(name='Reviewer 1', role='reviewer'))
            db.session.add(Contact(name='Company Rep', role='company_rep'))
            db.session.commit()

        response = client.get('/contacts/?role=reviewer')
        assert response.status_code == 200
        assert b'Reviewer 1' in response.data


class TestCompanyRoutes:
    """Tests for company routes."""

    def test_list_companies_empty(self, client):
        """Test company list with no data."""
        response = client.get('/companies/')
        assert response.status_code == 200

    def test_create_company(self, client, app):
        """Test creating a new company."""
        response = client.post('/companies/new', data={
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

    def test_create_duplicate_company_fails(self, client, app):
        """Test that duplicate company names are rejected."""
        with app.app_context():
            company = Company(name='Logitech')
            db.session.add(company)
            db.session.commit()

        response = client.post('/companies/new', data={
            'name': 'Logitech',
            'category': 'mice',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already exists' in response.data

    def test_edit_company(self, client, app):
        """Test editing a company."""
        with app.app_context():
            company = Company(name='Test Co', affiliate_status='no')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post(f'/companies/{company_id}/edit', data={
            'name': 'Test Co',
            'category': 'keyboards',
            'affiliate_status': 'yes',
            'affiliate_link': 'https://test.com?ref=dazz',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            company = Company.query.get(company_id)
            assert company.category == 'keyboards'
            assert company.affiliate_status == 'yes'

    def test_delete_company(self, client, app):
        """Test deleting a company."""
        with app.app_context():
            company = Company(name='To Delete')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post(f'/companies/{company_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            company = Company.query.get(company_id)
            assert company is None


class TestInventoryRoutes:
    """Tests for inventory routes."""

    def test_list_inventory_empty(self, client):
        """Test inventory list with no data."""
        response = client.get('/inventory/')
        assert response.status_code == 200

    def test_create_review_unit(self, client, app):
        """Test creating a review unit."""
        response = client.post('/inventory/new', data={
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

    def test_create_personal_purchase(self, client, app):
        """Test creating a personal purchase."""
        response = client.post('/inventory/new', data={
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

    def test_create_item_with_company(self, client, app):
        """Test creating inventory linked to company."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post('/inventory/new', data={
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

    def test_create_item_with_content_links(self, client, app):
        """Test creating inventory with video links."""
        response = client.post('/inventory/new', data={
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

    def test_create_sold_item(self, client, app):
        """Test creating a sold item with P/L tracking."""
        response = client.post('/inventory/new', data={
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

    def test_edit_item(self, client, app):
        """Test editing an inventory item."""
        with app.app_context():
            item = Inventory(product_name='Old Name', status='in_queue')
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = client.post(f'/inventory/{item_id}/edit', data={
            'product_name': 'New Name',
            'category': 'keyboard',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'reviewing',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.get(item_id)
            assert item.product_name == 'New Name'
            assert item.category == 'keyboard'
            assert item.status == 'reviewing'

    def test_delete_item(self, client, app):
        """Test deleting an inventory item."""
        with app.app_context():
            item = Inventory(product_name='To Delete')
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = client.post(f'/inventory/{item_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.get(item_id)
            assert item is None

    def test_mark_sold_action(self, client, app):
        """Test quick mark-as-sold action."""
        with app.app_context():
            item = Inventory(product_name='To Sell', status='listed')
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = client.post(f'/inventory/{item_id}/mark-sold', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.get(item_id)
            assert item.sold is True
            assert item.status == 'sold'

    def test_filter_by_source_type(self, client, app):
        """Test filtering inventory by source type."""
        with app.app_context():
            db.session.add(Inventory(product_name='Review Unit', source_type='review_unit'))
            db.session.add(Inventory(product_name='Personal', source_type='personal_purchase'))
            db.session.commit()

        response = client.get('/inventory/?source_type=review_unit')
        assert response.status_code == 200
        assert b'Review Unit' in response.data

    def test_filter_by_sold_status(self, client, app):
        """Test filtering inventory by sold status."""
        with app.app_context():
            db.session.add(Inventory(product_name='Unsold Item', sold=False))
            db.session.add(Inventory(product_name='Sold Item', sold=True))
            db.session.commit()

        response = client.get('/inventory/?sold=yes')
        assert response.status_code == 200
        assert b'Sold Item' in response.data
