"""Tests for affiliate revenue routes - focusing on validation and error paths."""
import pytest
from models import AffiliateRevenue, Company
from extensions import db


@pytest.fixture
def affiliate_company(app):
    """Create a company with affiliate status."""
    with app.app_context():
        c = Company(name='Affiliate Test Co', affiliate_status='yes')
        db.session.add(c)
        db.session.commit()
        return {'id': c.id, 'name': c.name}


@pytest.fixture
def revenue_entry(app, affiliate_company):
    """Create a test revenue entry."""
    with app.app_context():
        entry = AffiliateRevenue(
            company_id=affiliate_company['id'],
            year=2024,
            month=1,
            revenue=100.50,
            sales_count=10
        )
        db.session.add(entry)
        db.session.commit()
        return {'id': entry.id, 'company_id': affiliate_company['id']}


class TestNewRevenueValidation:
    """Tests for validation in new revenue creation."""

    def test_create_revenue_missing_company(self, auth_client):
        """Test creating revenue without company fails."""
        response = auth_client.post('/affiliates/new', data={
            'year': '2024',
            'month': '1',
            'revenue': '100.00'
        })
        assert response.status_code == 200
        # Should show company required error

    def test_create_revenue_missing_year(self, auth_client, affiliate_company):
        """Test creating revenue without year fails."""
        response = auth_client.post('/affiliates/new', data={
            'company_id': affiliate_company['id'],
            'month': '1',
            'revenue': '100.00'
        })
        assert response.status_code == 200
        # Should show year required error

    def test_create_revenue_missing_month(self, auth_client, affiliate_company):
        """Test creating revenue without month fails."""
        response = auth_client.post('/affiliates/new', data={
            'company_id': affiliate_company['id'],
            'year': '2024',
            'revenue': '100.00'
        })
        assert response.status_code == 200
        # Should show month required error

    def test_create_revenue_missing_revenue(self, auth_client, affiliate_company):
        """Test creating revenue without revenue amount fails."""
        response = auth_client.post('/affiliates/new', data={
            'company_id': affiliate_company['id'],
            'year': '2024',
            'month': '1'
        })
        assert response.status_code == 200
        # Should show revenue required error

    def test_create_revenue_invalid_month(self, auth_client, affiliate_company):
        """Test creating revenue with invalid month fails."""
        response = auth_client.post('/affiliates/new', data={
            'company_id': affiliate_company['id'],
            'year': '2024',
            'month': '13',  # Invalid month
            'revenue': '100.00'
        })
        assert response.status_code == 200
        # Should show validation error

    def test_create_revenue_invalid_year(self, auth_client, affiliate_company):
        """Test creating revenue with invalid year fails."""
        response = auth_client.post('/affiliates/new', data={
            'company_id': affiliate_company['id'],
            'year': '1999',  # Before 2000
            'month': '1',
            'revenue': '100.00'
        })
        assert response.status_code == 200
        # Should show validation error

    def test_create_duplicate_entry(self, auth_client, app, revenue_entry, affiliate_company):
        """Test creating duplicate entry for same company/month fails."""
        response = auth_client.post('/affiliates/new', data={
            'company_id': affiliate_company['id'],
            'year': '2024',  # Same as fixture
            'month': '1',    # Same as fixture
            'revenue': '200.00'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'already exists' in response.data.lower()


class TestEditRevenueValidation:
    """Tests for validation in revenue editing."""

    def test_edit_revenue_missing_revenue(self, auth_client, revenue_entry):
        """Test editing revenue without revenue amount fails."""
        response = auth_client.post(f'/affiliates/{revenue_entry["id"]}/edit', data={
            'revenue': ''  # Empty revenue
        })
        assert response.status_code == 200
        # Should show error

    def test_edit_revenue_success(self, auth_client, app, revenue_entry):
        """Test successful revenue edit."""
        response = auth_client.post(f'/affiliates/{revenue_entry["id"]}/edit', data={
            'revenue': '200.00',
            'sales_count': '20',
            'notes': 'Updated notes'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data.lower()

        with app.app_context():
            entry = db.session.get(AffiliateRevenue, revenue_entry['id'])
            assert entry.revenue == 200.00
            assert entry.sales_count == 20

    def test_edit_nonexistent_404(self, auth_client):
        """Test editing non-existent entry returns 404."""
        response = auth_client.get('/affiliates/99999/edit')
        assert response.status_code == 404


class TestDeleteRevenue:
    """Tests for revenue deletion."""

    def test_delete_revenue_success(self, auth_client, app, revenue_entry):
        """Test deleting revenue entry."""
        entry_id = revenue_entry['id']
        response = auth_client.post(f'/affiliates/{entry_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            deleted = db.session.get(AffiliateRevenue, entry_id)
            assert deleted is None

    def test_delete_nonexistent_404(self, auth_client):
        """Test deleting non-existent entry returns 404."""
        response = auth_client.post('/affiliates/99999/delete')
        assert response.status_code == 404


class TestListRevenueFiltering:
    """Tests for revenue listing with filters."""

    def test_list_revenue_filter_by_company(self, auth_client, app, revenue_entry, affiliate_company):
        """Test filtering by company."""
        response = auth_client.get(f'/affiliates/?company_id={affiliate_company["id"]}')
        assert response.status_code == 200

    def test_list_revenue_filter_by_year(self, auth_client, app, revenue_entry):
        """Test filtering by year."""
        response = auth_client.get('/affiliates/?year=2024')
        assert response.status_code == 200

    def test_list_revenue_pagination(self, auth_client, app, affiliate_company):
        """Test pagination."""
        with app.app_context():
            for i in range(5):
                entry = AffiliateRevenue(
                    company_id=affiliate_company['id'],
                    year=2024,
                    month=i + 2,
                    revenue=100.00
                )
                db.session.add(entry)
            db.session.commit()

        response = auth_client.get('/affiliates/?page=1')
        assert response.status_code == 200


class TestRevenueAuth:
    """Tests for authentication requirements."""

    def test_list_revenue_requires_auth(self, client):
        """Test list requires authentication."""
        response = client.get('/affiliates/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_new_revenue_requires_auth(self, client):
        """Test new requires authentication."""
        response = client.get('/affiliates/new')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_edit_revenue_requires_auth(self, client, revenue_entry):
        """Test edit requires authentication."""
        response = client.get(f'/affiliates/{revenue_entry["id"]}/edit')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_revenue_requires_auth(self, client, revenue_entry):
        """Test delete requires authentication."""
        response = client.post(f'/affiliates/{revenue_entry["id"]}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location
