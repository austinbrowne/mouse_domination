import pytest
from datetime import date
from app import db
from models import Contact, Company, Inventory, AffiliateRevenue, User


class TestCompanyModel:
    """Tests for Company model."""

    def test_create_company(self, app):
        """Test creating a company."""
        with app.app_context():
            company = Company(
                name='Pulsar',
                category='mice',
                website='https://pulsar.gg',
                relationship_status='active',
                affiliate_status='yes',
                affiliate_code='DAZZ10',
                commission_rate=10.0,
            )
            db.session.add(company)
            db.session.commit()

            assert company.id is not None
            assert company.name == 'Pulsar'
            assert company.category == 'mice'
            assert company.commission_rate == 10.0

    def test_company_defaults(self, app):
        """Test company default values."""
        with app.app_context():
            company = Company(name='Test Company')
            db.session.add(company)
            db.session.commit()

            assert company.category == 'mice'
            assert company.relationship_status == 'no_contact'
            assert company.affiliate_status == 'no'
            assert company.priority == 'low'

    def test_company_to_dict(self, app):
        """Test company serialization."""
        with app.app_context():
            company = Company(
                name='Razer',
                category='mice',
                affiliate_link='https://razer.com?ref=dazz',
            )
            db.session.add(company)
            db.session.commit()

            data = company.to_dict()
            assert data['name'] == 'Razer'
            assert data['category'] == 'mice'
            assert data['affiliate_link'] == 'https://razer.com?ref=dazz'
            assert 'created_at' in data


class TestContactModel:
    """Tests for Contact model."""

    def test_create_contact(self, app):
        """Test creating a contact."""
        with app.app_context():
            contact = Contact(
                name='ManPhalanges',
                role='reviewer',
                twitter='@manphalanges',
                relationship_status='close',
            )
            db.session.add(contact)
            db.session.commit()

            assert contact.id is not None
            assert contact.name == 'ManPhalanges'
            assert contact.role == 'reviewer'

    def test_contact_with_company(self, app):
        """Test contact linked to company."""
        with app.app_context():
            company = Company(name='Logitech')
            db.session.add(company)
            db.session.commit()

            contact = Contact(
                name='John Doe',
                role='company_rep',
                company_id=company.id,
                email='john@logitech.com',
            )
            db.session.add(contact)
            db.session.commit()

            assert contact.company.name == 'Logitech'
            assert contact in company.contacts

    def test_contact_defaults(self, app):
        """Test contact default values."""
        with app.app_context():
            contact = Contact(name='Test Person')
            db.session.add(contact)
            db.session.commit()

            assert contact.role == 'other'
            assert contact.relationship_status == 'cold'

    def test_contact_to_dict(self, app):
        """Test contact serialization."""
        with app.app_context():
            contact = Contact(
                name='Aimadapt',
                role='reviewer',
                youtube='https://youtube.com/@aimadapt',
                tags='collab,friend',
            )
            db.session.add(contact)
            db.session.commit()

            data = contact.to_dict()
            assert data['name'] == 'Aimadapt'
            assert data['role'] == 'reviewer'
            assert data['tags'] == 'collab,friend'


class TestInventoryModel:
    """Tests for Inventory model."""

    def test_create_review_unit(self, app, test_user):
        """Test creating a review unit."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(
                product_name='Pulsar X2',
                category='mouse',
                source_type='review_unit',
                cost=0.0,
                status='in_queue',
                user_id=user.id,
            )
            db.session.add(item)
            db.session.commit()

            assert item.id is not None
            assert item.product_name == 'Pulsar X2'
            assert item.source_type == 'review_unit'
            assert item.cost == 0.0

    def test_create_personal_purchase(self, app, test_user):
        """Test creating a personal purchase."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(
                product_name='GPX Superlight',
                category='mouse',
                source_type='personal_purchase',
                cost=149.99,
                date_acquired=date(2025, 6, 15),
                user_id=user.id,
            )
            db.session.add(item)
            db.session.commit()

            assert item.source_type == 'personal_purchase'
            assert item.cost == 149.99

    def test_inventory_with_company(self, app, test_user):
        """Test inventory linked to company."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()

            item = Inventory(
                product_name='Pulsar X2',
                company_id=company.id,
                source_type='review_unit',
                user_id=user.id,
            )
            db.session.add(item)
            db.session.commit()

            assert item.company.name == 'Pulsar'
            assert item in company.inventory_items

    def test_profit_loss_calculation_unsold(self, app, test_user):
        """Test P/L calculation for unsold item."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            # Review unit (free) - no loss
            item1 = Inventory(
                product_name='Free Mouse',
                source_type='review_unit',
                cost=0.0,
                sold=False,
                user_id=user.id,
            )
            db.session.add(item1)

            # Personal purchase - shows cost as loss
            item2 = Inventory(
                product_name='Bought Mouse',
                source_type='personal_purchase',
                cost=100.0,
                sold=False,
                user_id=user.id,
            )
            db.session.add(item2)
            db.session.commit()

            assert item1.profit_loss == 0.0
            assert item2.profit_loss == -100.0

    def test_profit_loss_calculation_sold(self, app, test_user):
        """Test P/L calculation for sold item."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            # Sold review unit - pure profit
            item1 = Inventory(
                product_name='Sold Review Unit',
                source_type='review_unit',
                cost=0.0,
                sold=True,
                sale_price=80.0,
                fees=10.0,
                shipping=5.0,
                user_id=user.id,
            )
            db.session.add(item1)

            # Sold personal purchase
            item2 = Inventory(
                product_name='Sold Purchase',
                source_type='personal_purchase',
                cost=100.0,
                sold=True,
                sale_price=85.0,
                fees=12.0,
                shipping=0.0,  # Buyer paid
                user_id=user.id,
            )
            db.session.add(item2)
            db.session.commit()

            # 80 - 10 - 5 - 0 = 65
            assert item1.profit_loss == 65.0

            # 85 - 12 - 0 - 100 = -27
            assert item2.profit_loss == -27.0

    def test_profit_loss_with_none_values(self, app, test_user):
        """Test P/L handles None values gracefully."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(
                product_name='Test',
                sold=True,
                sale_price=50.0,
                fees=None,
                shipping=None,
                cost=None,
                user_id=user.id,
            )
            db.session.add(item)
            db.session.commit()

            # 50 - 0 - 0 - 0 = 50
            assert item.profit_loss == 50.0

    def test_inventory_defaults(self, app, test_user):
        """Test inventory default values."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(product_name='Test Mouse', user_id=user.id)
            db.session.add(item)
            db.session.commit()

            assert item.category == 'mouse'
            assert item.source_type == 'review_unit'
            assert item.cost == 0.0
            assert item.on_amazon is False
            assert item.status == 'in_queue'
            assert item.condition == 'new'
            assert item.sold is False

    def test_inventory_content_links(self, app, test_user):
        """Test inventory with content links."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(
                product_name='Reviewed Mouse',
                status='reviewed',
                short_url='https://youtube.com/shorts/abc123',
                short_publish_date=date(2025, 3, 8),
                video_url='https://youtube.com/watch?v=xyz789',
                video_publish_date=date(2025, 3, 19),
                user_id=user.id,
            )
            db.session.add(item)
            db.session.commit()

            assert item.short_url == 'https://youtube.com/shorts/abc123'
            assert item.video_publish_date == date(2025, 3, 19)

    def test_inventory_to_dict(self, app, test_user):
        """Test inventory serialization."""
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            item = Inventory(
                product_name='Serialized Mouse',
                category='mouse',
                sold=True,
                sale_price=100.0,
                fees=10.0,
                shipping=5.0,
                cost=0.0,
                user_id=user.id,
            )
            db.session.add(item)
            db.session.commit()

            data = item.to_dict()
            assert data['product_name'] == 'Serialized Mouse'
            assert data['profit_loss'] == 85.0
            assert 'created_at' in data


class TestAffiliateRevenueModel:
    """Tests for AffiliateRevenue model."""

    def test_create_revenue_entry(self, app):
        """Test creating affiliate revenue entry."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()

            revenue = AffiliateRevenue(
                company_id=company.id,
                year=2025,
                month=6,
                revenue=150.0,
                sales_count=5,
            )
            db.session.add(revenue)
            db.session.commit()

            assert revenue.id is not None
            assert revenue.revenue == 150.0
            assert revenue.sales_count == 5

    def test_revenue_company_relationship(self, app):
        """Test revenue linked to company."""
        with app.app_context():
            company = Company(name='MCHOSE')
            db.session.add(company)
            db.session.commit()

            revenue = AffiliateRevenue(
                company_id=company.id,
                year=2025,
                month=1,
                revenue=75.0,
            )
            db.session.add(revenue)
            db.session.commit()

            assert revenue.company.name == 'MCHOSE'
            assert revenue in company.affiliate_revenues

    def test_month_year_property(self, app):
        """Test month_year formatted string."""
        with app.app_context():
            company = Company(name='Test')
            db.session.add(company)
            db.session.commit()

            revenue = AffiliateRevenue(
                company_id=company.id,
                year=2025,
                month=12,
                revenue=100.0,
            )
            db.session.add(revenue)
            db.session.commit()

            assert revenue.month_year == 'Dec 2025'

    def test_unique_constraint(self, app):
        """Test unique constraint on company/year/month."""
        with app.app_context():
            company = Company(name='Test')
            db.session.add(company)
            db.session.commit()

            rev1 = AffiliateRevenue(company_id=company.id, year=2025, month=6, revenue=100.0)
            db.session.add(rev1)
            db.session.commit()

            # Try to add duplicate
            rev2 = AffiliateRevenue(company_id=company.id, year=2025, month=6, revenue=200.0)
            db.session.add(rev2)

            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()

    def test_revenue_to_dict(self, app):
        """Test revenue serialization."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()

            revenue = AffiliateRevenue(
                company_id=company.id,
                year=2025,
                month=3,
                revenue=125.50,
            )
            db.session.add(revenue)
            db.session.commit()

            data = revenue.to_dict()
            assert data['company_name'] == 'Pulsar'
            assert data['revenue'] == 125.50
            assert data['month_year'] == 'Mar 2025'
