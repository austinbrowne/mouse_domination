"""Tests for pipeline (sales) routes."""
import pytest
from models import SalesPipeline, Company, Contact
from extensions import db


@pytest.fixture
def deal(app, company, contact, test_user):
    """Create a test pipeline deal owned by test_user."""
    with app.app_context():
        d = SalesPipeline(
            user_id=test_user['id'],
            company_id=company['id'],
            contact_id=contact['id'],
            deal_type='podcast_ad',
            status='lead',
            rate_quoted=500.00
        )
        db.session.add(d)
        db.session.commit()
        return {'id': d.id, 'company_id': company['id']}


class TestListDeals:
    """Tests for deal listing."""

    def test_list_deals_requires_auth(self, client):
        """Test list requires authentication."""
        response = client.get('/pipeline/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_deals_empty(self, auth_client):
        """Test list with no deals."""
        response = auth_client.get('/pipeline/')
        assert response.status_code == 200

    def test_list_deals_with_data(self, auth_client, deal):
        """Test list shows deals."""
        response = auth_client.get('/pipeline/')
        assert response.status_code == 200

    def test_filter_by_deal_type(self, auth_client, app, company):
        """Test filtering by deal type."""
        with app.app_context():
            d1 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='lead')
            d2 = SalesPipeline(company_id=company['id'], deal_type='paid_review', status='lead')
            db.session.add_all([d1, d2])
            db.session.commit()

        response = auth_client.get('/pipeline/?type=podcast_ad')
        assert response.status_code == 200
        # Just verify the page loads with filter

    def test_filter_by_status(self, auth_client, app, company):
        """Test filtering by status."""
        with app.app_context():
            d1 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='lead')
            d2 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='completed')
            db.session.add_all([d1, d2])
            db.session.commit()

        response = auth_client.get('/pipeline/?status=lead')
        assert response.status_code == 200

    def test_filter_by_payment_status(self, auth_client, app, company):
        """Test filtering by payment status."""
        with app.app_context():
            d1 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='completed', payment_status='paid')
            d2 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='completed', payment_status='pending')
            db.session.add_all([d1, d2])
            db.session.commit()

        response = auth_client.get('/pipeline/?payment=paid')
        assert response.status_code == 200

    def test_filter_follow_up(self, auth_client, app, company):
        """Test filtering by follow_up=yes."""
        with app.app_context():
            d1 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='lead', follow_up_needed=True)
            d2 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='lead', follow_up_needed=False)
            db.session.add_all([d1, d2])
            db.session.commit()

        response = auth_client.get('/pipeline/?follow_up=yes')
        assert response.status_code == 200

    def test_pagination(self, auth_client, app, company):
        """Test pagination works."""
        with app.app_context():
            for i in range(5):
                d = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='lead')
                db.session.add(d)
            db.session.commit()

        response = auth_client.get('/pipeline/?page=1')
        assert response.status_code == 200

    def test_stats_calculation(self, auth_client, app, company):
        """Test stats are calculated."""
        with app.app_context():
            d1 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='lead', rate_quoted=100)
            d2 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='negotiating', rate_quoted=200)
            d3 = SalesPipeline(company_id=company['id'], deal_type='podcast_ad', status='completed', rate_agreed=300)
            db.session.add_all([d1, d2, d3])
            db.session.commit()

        response = auth_client.get('/pipeline/')
        assert response.status_code == 200

    def test_invalid_filter_ignored(self, auth_client, deal):
        """Test invalid filter values are ignored."""
        response = auth_client.get('/pipeline/?type=invalid_type&status=invalid_status')
        assert response.status_code == 200


class TestNewDeal:
    """Tests for creating new deals."""

    def test_new_deal_form_renders(self, auth_client):
        """Test new deal form renders."""
        response = auth_client.get('/pipeline/new')
        assert response.status_code == 200

    def test_create_deal_success(self, auth_client, app, company):
        """Test creating a new deal."""
        response = auth_client.post('/pipeline/new', data={
            'company_id': company['id'],
            'deal_type': 'podcast_ad',
            'status': 'lead',
            'rate_quoted': '500.00'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'created successfully' in response.data.lower()

        with app.app_context():
            deal = SalesPipeline.query.filter_by(company_id=company['id']).first()
            assert deal is not None
            assert deal.deal_type == 'podcast_ad'

    def test_create_deal_missing_company(self, auth_client):
        """Test creating deal without company fails."""
        response = auth_client.post('/pipeline/new', data={
            'deal_type': 'podcast_ad',
            'status': 'lead'
        })
        assert response.status_code == 200
        # Should show error

    def test_create_deal_invalid_company(self, auth_client):
        """Test creating deal with invalid company ID."""
        response = auth_client.post('/pipeline/new', data={
            'company_id': '99999',
            'deal_type': 'podcast_ad',
            'status': 'lead'
        })
        assert response.status_code == 200
        # Should show validation error

    def test_create_deal_with_contact(self, auth_client, app, company, contact):
        """Test creating deal with contact."""
        response = auth_client.post('/pipeline/new', data={
            'company_id': company['id'],
            'contact_id': contact['id'],
            'deal_type': 'podcast_ad',
            'status': 'lead'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            deal = SalesPipeline.query.filter_by(company_id=company['id']).first()
            assert deal.contact_id == contact['id']

    def test_create_deal_with_all_fields(self, auth_client, app, company):
        """Test creating deal with all optional fields."""
        response = auth_client.post('/pipeline/new', data={
            'company_id': company['id'],
            'deal_type': 'paid_review',
            'status': 'negotiating',
            'rate_quoted': '1000.00',
            'rate_agreed': '800.00',
            'deliverables': 'Video review + social posts',
            'deadline': '2024-12-31',
            'payment_status': 'pending',
            'notes': 'Important deal',
            'follow_up_needed': 'on',
            'follow_up_date': '2024-06-15'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            deal = SalesPipeline.query.filter_by(company_id=company['id']).first()
            assert deal.rate_quoted == 1000.00
            assert deal.rate_agreed == 800.00
            assert deal.follow_up_needed is True


class TestEditDeal:
    """Tests for editing deals."""

    def test_edit_deal_form_renders(self, auth_client, deal):
        """Test edit form renders with deal data."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/edit')
        assert response.status_code == 200

    def test_edit_deal_nonexistent_404(self, auth_client):
        """Test editing non-existent deal returns 404."""
        response = auth_client.get('/pipeline/99999/edit')
        assert response.status_code == 404

    def test_update_deal_success(self, auth_client, app, deal):
        """Test updating a deal."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/edit', data={
            'company_id': deal['company_id'],
            'deal_type': 'paid_review',
            'status': 'completed',
            'rate_quoted': '600.00',
            'rate_agreed': '550.00'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data.lower()

        with app.app_context():
            updated = db.session.get(SalesPipeline, deal['id'])
            assert updated.status == 'completed'
            assert updated.rate_agreed == 550.00

    def test_update_deal_missing_company(self, auth_client, deal):
        """Test updating deal without company fails."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/edit', data={
            'deal_type': 'podcast_ad',
            'status': 'lead'
        })
        assert response.status_code == 200
        # Should show error

    def test_update_deal_change_status(self, auth_client, app, deal):
        """Test changing deal status."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/edit', data={
            'company_id': deal['company_id'],
            'deal_type': 'podcast_ad',
            'status': 'negotiating'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            updated = db.session.get(SalesPipeline, deal['id'])
            assert updated.status == 'negotiating'


class TestDeleteDeal:
    """Tests for deleting deals."""

    def test_delete_deal_success(self, auth_client, app, deal):
        """Test deleting a deal."""
        deal_id = deal['id']
        response = auth_client.post(f'/pipeline/{deal_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            deleted = db.session.get(SalesPipeline, deal_id)
            assert deleted is None

    def test_delete_nonexistent_404(self, auth_client):
        """Test deleting non-existent deal returns 404."""
        response = auth_client.post('/pipeline/99999/delete')
        assert response.status_code == 404

    def test_delete_redirects_to_list(self, auth_client, deal):
        """Test delete redirects to list."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/delete')
        assert response.status_code == 302
        assert '/pipeline/' in response.location


class TestQuickActions:
    """Tests for quick action routes."""

    def test_mark_complete(self, auth_client, app, deal):
        """Test marking deal as completed."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/mark-complete', follow_redirects=True)
        assert response.status_code == 200
        assert b'completed' in response.data.lower()

        with app.app_context():
            updated = db.session.get(SalesPipeline, deal['id'])
            assert updated.status == 'completed'

    def test_mark_complete_nonexistent_404(self, auth_client):
        """Test marking non-existent deal returns 404."""
        response = auth_client.post('/pipeline/99999/mark-complete')
        assert response.status_code == 404

    def test_mark_paid(self, auth_client, app, deal):
        """Test marking deal as paid."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/mark-paid', follow_redirects=True)
        assert response.status_code == 200
        assert b'paid' in response.data.lower()

        with app.app_context():
            updated = db.session.get(SalesPipeline, deal['id'])
            assert updated.payment_status == 'paid'
            assert updated.payment_date is not None

    def test_mark_paid_nonexistent_404(self, auth_client):
        """Test marking non-existent deal as paid returns 404."""
        response = auth_client.post('/pipeline/99999/mark-paid')
        assert response.status_code == 404

    def test_mark_complete_redirects(self, auth_client, deal):
        """Test mark complete redirects to list."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/mark-complete')
        assert response.status_code == 302
        assert '/pipeline/' in response.location

    def test_mark_paid_redirects(self, auth_client, deal):
        """Test mark paid redirects to list."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/mark-paid')
        assert response.status_code == 302
        assert '/pipeline/' in response.location
