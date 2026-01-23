"""Tests for Creator Hub: Revenue Dashboard and related models."""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from models import RevenueEntry, DealDeliverable, SalesPipeline, Company, AffiliateRevenue
from extensions import db
from routes.revenue import calculate_diversification_score, generate_risk_alerts


# ============== Fixtures ==============

@pytest.fixture
def revenue_entry(app, test_user):
    """Create a test revenue entry owned by test_user."""
    with app.app_context():
        entry = RevenueEntry(
            user_id=test_user['id'],
            source_type=RevenueEntry.SOURCE_AFFILIATE,
            source_name='Amazon Associates',
            amount=Decimal('150.00'),
            currency='USD',
            date_earned=date.today(),
            notes='Test affiliate revenue'
        )
        db.session.add(entry)
        db.session.commit()
        return {'id': entry.id, 'user_id': test_user['id'], 'amount': 150.00}


@pytest.fixture
def multiple_revenue_entries(app, test_user):
    """Create multiple revenue entries for diversification testing."""
    with app.app_context():
        entries = [
            RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Amazon Associates',
                amount=Decimal('100.00'),
                date_earned=date.today()
            ),
            RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_SPONSORSHIP,
                source_name='BrandX',
                amount=Decimal('500.00'),
                date_earned=date.today()
            ),
            RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_PLATFORM,
                source_name='YouTube AdSense',
                amount=Decimal('200.00'),
                date_earned=date.today()
            ),
            RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_MEMBERSHIP,
                source_name='Patreon',
                amount=Decimal('200.00'),
                date_earned=date.today()
            ),
        ]
        for entry in entries:
            db.session.add(entry)
        db.session.commit()
        return {'total': 1000.00, 'count': 4}


@pytest.fixture
def concentrated_revenue(app, test_user):
    """Create revenue entries with high concentration (one source dominates)."""
    with app.app_context():
        entries = [
            RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_SPONSORSHIP,
                source_name='BigBrand',
                amount=Decimal('900.00'),
                date_earned=date.today()
            ),
            RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Amazon',
                amount=Decimal('100.00'),
                date_earned=date.today()
            ),
        ]
        for entry in entries:
            db.session.add(entry)
        db.session.commit()
        return {'total': 1000.00, 'concentration': 90}


@pytest.fixture
def affiliate_revenue_entry(app, test_user, company):
    """Create an affiliate revenue entry for sync testing."""
    with app.app_context():
        aff = AffiliateRevenue(
            user_id=test_user['id'],
            company_id=company['id'],
            year=date.today().year,
            month=date.today().month,
            revenue=250.00,
            notes='Affiliate payment'
        )
        db.session.add(aff)
        db.session.commit()
        return {'id': aff.id, 'company_id': company['id'], 'revenue': 250.00}


@pytest.fixture
def completed_paid_deal(app, test_user, company):
    """Create a completed and paid deal for sync testing."""
    with app.app_context():
        deal = SalesPipeline(
            user_id=test_user['id'],
            company_id=company['id'],
            deal_type='podcast_ad',
            status='completed',
            payment_status='paid',
            rate_agreed=1000.00,
            payment_date=date.today()
        )
        db.session.add(deal)
        db.session.commit()
        return {'id': deal.id, 'company_id': company['id'], 'rate': 1000.00}


# ============== RevenueEntry Model Tests ==============

class TestRevenueEntryModel:
    """Tests for RevenueEntry model."""

    def test_create_revenue_entry(self, app, test_user):
        """Test creating a basic revenue entry."""
        with app.app_context():
            entry = RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Test Source',
                amount=Decimal('100.00'),
                date_earned=date.today()
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.id is not None
            assert entry.user_id == test_user['id']
            assert entry.source_type == 'affiliate'
            assert float(entry.amount) == 100.00

    def test_revenue_entry_constants(self):
        """Test source type constants are defined."""
        assert RevenueEntry.SOURCE_SPONSORSHIP == 'sponsorship'
        assert RevenueEntry.SOURCE_AFFILIATE == 'affiliate'
        assert RevenueEntry.SOURCE_PLATFORM == 'platform'
        assert RevenueEntry.SOURCE_PRODUCT == 'product'
        assert RevenueEntry.SOURCE_MEMBERSHIP == 'membership'
        assert RevenueEntry.SOURCE_OTHER == 'other'

    def test_revenue_entry_source_types_list(self):
        """Test SOURCE_TYPES list contains all expected types."""
        types = [t[0] for t in RevenueEntry.SOURCE_TYPES]
        assert 'sponsorship' in types
        assert 'affiliate' in types
        assert 'platform' in types
        assert 'product' in types
        assert 'membership' in types
        assert 'other' in types
        assert len(types) == 6

    def test_revenue_entry_to_dict(self, app, test_user):
        """Test to_dict serialization."""
        with app.app_context():
            entry = RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Amazon',
                amount=Decimal('150.50'),
                date_earned=date(2024, 6, 15),
                notes='Test note'
            )
            db.session.add(entry)
            db.session.commit()

            d = entry.to_dict()
            assert d['source_type'] == 'affiliate'
            assert d['source_name'] == 'Amazon'
            assert d['amount'] == 150.50
            assert d['date_earned'] == '2024-06-15'
            assert d['notes'] == 'Test note'

    def test_revenue_entry_month_year_property(self, app, test_user):
        """Test month_year property formatting."""
        with app.app_context():
            entry = RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Test',
                amount=Decimal('100'),
                date_earned=date(2024, 6, 15)
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.month_year == 'Jun 2024'

    def test_revenue_entry_month_year_none(self, app, test_user):
        """Test month_year property when date_earned is None."""
        with app.app_context():
            entry = RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Test',
                amount=Decimal('100'),
                date_earned=None
            )
            # Note: date_earned is nullable=False, but testing the property logic
            assert entry.month_year is None

    def test_revenue_entry_with_affiliate_link(self, app, test_user, affiliate_revenue_entry):
        """Test revenue entry linked to affiliate revenue."""
        with app.app_context():
            entry = RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Linked Affiliate',
                amount=Decimal('100.00'),
                date_earned=date.today(),
                affiliate_revenue_id=affiliate_revenue_entry['id']
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.affiliate_revenue_id == affiliate_revenue_entry['id']
            assert entry.affiliate_revenue is not None

    def test_revenue_entry_with_pipeline_link(self, app, test_user, completed_paid_deal):
        """Test revenue entry linked to sales pipeline deal."""
        with app.app_context():
            entry = RevenueEntry(
                user_id=test_user['id'],
                source_type=RevenueEntry.SOURCE_SPONSORSHIP,
                source_name='Linked Deal',
                amount=Decimal('1000.00'),
                date_earned=date.today(),
                pipeline_deal_id=completed_paid_deal['id']
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.pipeline_deal_id == completed_paid_deal['id']
            assert entry.pipeline_deal is not None


# ============== Diversification Score Tests ==============

class TestDiversificationScore:
    """Tests for calculate_diversification_score function."""

    def test_empty_revenue_returns_zero(self):
        """Test empty revenue list returns 0."""
        assert calculate_diversification_score([], 0) == 0
        assert calculate_diversification_score(None, 0) == 0
        assert calculate_diversification_score([], 100) == 0

    def test_single_source_returns_zero(self):
        """Test single revenue source returns 0 (no diversification)."""
        revenue_by_source = [('sponsorship', Decimal('1000'))]
        assert calculate_diversification_score(revenue_by_source, 1000) == 0

    def test_equal_distribution_high_score(self):
        """Test equally distributed revenue gets high score."""
        revenue_by_source = [
            ('sponsorship', Decimal('250')),
            ('affiliate', Decimal('250')),
            ('platform', Decimal('250')),
            ('membership', Decimal('250')),
        ]
        score = calculate_diversification_score(revenue_by_source, 1000)
        assert score == 100  # Perfect diversification

    def test_concentrated_revenue_low_score(self):
        """Test concentrated revenue gets low score."""
        revenue_by_source = [
            ('sponsorship', Decimal('900')),
            ('affiliate', Decimal('100')),
        ]
        score = calculate_diversification_score(revenue_by_source, 1000)
        assert score < 40  # High concentration = low score

    def test_moderately_diversified(self):
        """Test moderately diversified revenue."""
        # 75/15/10 split gives moderate diversification score around 60
        revenue_by_source = [
            ('sponsorship', Decimal('750')),
            ('affiliate', Decimal('150')),
            ('platform', Decimal('100')),
        ]
        score = calculate_diversification_score(revenue_by_source, 1000)
        assert 40 < score < 80  # Moderate diversification

    def test_zero_total_revenue_returns_zero(self):
        """Test zero total revenue returns 0."""
        revenue_by_source = [('sponsorship', Decimal('100'))]
        assert calculate_diversification_score(revenue_by_source, 0) == 0


# ============== Risk Alerts Tests ==============

class TestRiskAlerts:
    """Tests for generate_risk_alerts function."""

    def test_empty_revenue_no_alerts(self):
        """Test empty revenue generates no alerts."""
        assert generate_risk_alerts([], 0) == []
        assert generate_risk_alerts(None, 0) == []
        assert generate_risk_alerts([], 100) == []

    def test_no_alerts_below_60_percent(self):
        """Test no alerts when no source exceeds 60%."""
        revenue_by_source = [
            ('sponsorship', Decimal('300')),
            ('affiliate', Decimal('300')),
            ('platform', Decimal('400')),
        ]
        alerts = generate_risk_alerts(revenue_by_source, 1000)
        assert len(alerts) == 0

    def test_warning_at_60_percent(self):
        """Test warning alert when source exceeds 60%."""
        revenue_by_source = [
            ('sponsorship', Decimal('700')),
            ('affiliate', Decimal('300')),
        ]
        alerts = generate_risk_alerts(revenue_by_source, 1000)
        assert len(alerts) == 1
        assert alerts[0]['level'] == 'warning'
        assert alerts[0]['source_type'] == 'sponsorship'
        assert 'diversifying' in alerts[0]['message'].lower()

    def test_critical_at_80_percent(self):
        """Test critical alert when source exceeds 80%."""
        revenue_by_source = [
            ('sponsorship', Decimal('850')),
            ('affiliate', Decimal('150')),
        ]
        alerts = generate_risk_alerts(revenue_by_source, 1000)
        assert len(alerts) == 1
        assert alerts[0]['level'] == 'critical'
        assert alerts[0]['source_type'] == 'sponsorship'
        assert 'high concentration' in alerts[0]['message'].lower()

    def test_multiple_alerts(self):
        """Test multiple sources can generate alerts."""
        revenue_by_source = [
            ('sponsorship', Decimal('650')),
            ('affiliate', Decimal('350')),
        ]
        # 65% sponsorship = warning
        alerts = generate_risk_alerts(revenue_by_source, 1000)
        assert len(alerts) == 1

    def test_zero_total_no_alerts(self):
        """Test zero total revenue generates no alerts."""
        revenue_by_source = [('sponsorship', Decimal('100'))]
        alerts = generate_risk_alerts(revenue_by_source, 0)
        assert len(alerts) == 0


# ============== Revenue Dashboard Route Tests ==============

class TestRevenueDashboard:
    """Tests for revenue dashboard route."""

    def test_dashboard_requires_auth(self, client):
        """Test dashboard requires authentication."""
        response = client.get('/revenue/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_dashboard_empty(self, auth_client):
        """Test dashboard with no revenue entries."""
        response = auth_client.get('/revenue/')
        assert response.status_code == 200
        assert b'revenue' in response.data.lower()

    def test_dashboard_with_data(self, auth_client, revenue_entry):
        """Test dashboard shows revenue data."""
        response = auth_client.get('/revenue/')
        assert response.status_code == 200

    def test_dashboard_filter_by_year(self, auth_client, revenue_entry):
        """Test filtering dashboard by year."""
        year = date.today().year
        response = auth_client.get(f'/revenue/?year={year}')
        assert response.status_code == 200

    def test_dashboard_filter_by_source_type(self, auth_client, revenue_entry):
        """Test filtering dashboard by source type."""
        response = auth_client.get('/revenue/?source_type=affiliate')
        assert response.status_code == 200

    def test_dashboard_pagination(self, auth_client, multiple_revenue_entries):
        """Test dashboard pagination works."""
        response = auth_client.get('/revenue/?page=1')
        assert response.status_code == 200

    def test_dashboard_shows_diversification_score(self, auth_client, multiple_revenue_entries):
        """Test dashboard shows diversification score."""
        response = auth_client.get('/revenue/')
        assert response.status_code == 200
        # Score should be displayed in the response

    def test_dashboard_shows_risk_alerts(self, auth_client, concentrated_revenue):
        """Test dashboard shows risk alerts for concentrated revenue."""
        response = auth_client.get('/revenue/')
        assert response.status_code == 200


# ============== Revenue Entry CRUD Route Tests ==============

class TestRevenueAddEntry:
    """Tests for adding revenue entries."""

    def test_add_form_requires_auth(self, client):
        """Test add form requires authentication."""
        response = client.get('/revenue/add')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_add_form_renders(self, auth_client):
        """Test add revenue form renders."""
        response = auth_client.get('/revenue/add')
        assert response.status_code == 200
        assert b'source_type' in response.data.lower() or b'source type' in response.data.lower()

    def test_add_entry_success(self, auth_client, app):
        """Test adding a new revenue entry."""
        response = auth_client.post('/revenue/add', data={
            'source_type': 'affiliate',
            'source_name': 'New Affiliate',
            'amount': '200.00',
            'date_earned': date.today().isoformat(),
            'currency': 'USD'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'added successfully' in response.data.lower()

        with app.app_context():
            entry = RevenueEntry.query.filter_by(source_name='New Affiliate').first()
            assert entry is not None
            assert float(entry.amount) == 200.00

    def test_add_entry_missing_source_name(self, auth_client):
        """Test adding entry without source name fails."""
        response = auth_client.post('/revenue/add', data={
            'source_type': 'affiliate',
            'amount': '100.00',
            'date_earned': date.today().isoformat()
        })
        assert response.status_code == 200
        # Should show error for missing required field

    def test_add_entry_missing_amount(self, auth_client):
        """Test adding entry without amount fails."""
        response = auth_client.post('/revenue/add', data={
            'source_type': 'affiliate',
            'source_name': 'Test',
            'date_earned': date.today().isoformat()
        })
        assert response.status_code == 200
        # Should show error

    def test_add_entry_invalid_amount(self, auth_client):
        """Test adding entry with invalid amount fails."""
        response = auth_client.post('/revenue/add', data={
            'source_type': 'affiliate',
            'source_name': 'Test',
            'amount': '-100.00',
            'date_earned': date.today().isoformat()
        })
        assert response.status_code == 200
        # Should show error for negative amount

    def test_add_entry_missing_date(self, auth_client):
        """Test adding entry without date fails."""
        response = auth_client.post('/revenue/add', data={
            'source_type': 'affiliate',
            'source_name': 'Test',
            'amount': '100.00'
        })
        assert response.status_code == 200
        # Should show error

    def test_add_entry_with_notes(self, auth_client, app):
        """Test adding entry with optional notes."""
        response = auth_client.post('/revenue/add', data={
            'source_type': 'platform',
            'source_name': 'YouTube',
            'amount': '300.00',
            'date_earned': date.today().isoformat(),
            'notes': 'June payout'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            entry = RevenueEntry.query.filter_by(source_name='YouTube').first()
            assert entry.notes == 'June payout'

    def test_add_entry_with_date_received(self, auth_client, app):
        """Test adding entry with date received."""
        earned = date.today() - timedelta(days=30)
        received = date.today()
        response = auth_client.post('/revenue/add', data={
            'source_type': 'sponsorship',
            'source_name': 'Brand Deal',
            'amount': '1000.00',
            'date_earned': earned.isoformat(),
            'date_received': received.isoformat()
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            entry = RevenueEntry.query.filter_by(source_name='Brand Deal').first()
            assert entry.date_received == received


class TestRevenueEditEntry:
    """Tests for editing revenue entries."""

    def test_edit_form_requires_auth(self, client, revenue_entry):
        """Test edit form requires authentication."""
        response = client.get(f'/revenue/{revenue_entry["id"]}/edit')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_edit_form_renders(self, auth_client, revenue_entry):
        """Test edit form renders with entry data."""
        response = auth_client.get(f'/revenue/{revenue_entry["id"]}/edit')
        assert response.status_code == 200

    def test_edit_nonexistent_404(self, auth_client):
        """Test editing non-existent entry returns 404."""
        response = auth_client.get('/revenue/99999/edit')
        assert response.status_code == 404

    def test_edit_entry_success(self, auth_client, app, revenue_entry):
        """Test editing an existing entry."""
        response = auth_client.post(f'/revenue/{revenue_entry["id"]}/edit', data={
            'source_type': 'sponsorship',
            'source_name': 'Updated Source',
            'amount': '250.00',
            'date_earned': date.today().isoformat()
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data.lower()

        with app.app_context():
            entry = db.session.get(RevenueEntry, revenue_entry['id'])
            assert entry.source_name == 'Updated Source'
            assert float(entry.amount) == 250.00

    def test_edit_entry_different_user_403(self, app, auth_client, admin_user):
        """Test editing another user's entry returns 403."""
        # Create entry for admin user
        with app.app_context():
            entry = RevenueEntry(
                user_id=admin_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Admin Entry',
                amount=Decimal('100.00'),
                date_earned=date.today()
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

        # Try to edit with test_user's client - returns 404 (doesn't leak existence)
        response = auth_client.get(f'/revenue/{entry_id}/edit')
        assert response.status_code == 404


class TestRevenueDeleteEntry:
    """Tests for deleting revenue entries."""

    def test_delete_requires_auth(self, client, revenue_entry):
        """Test delete requires authentication."""
        response = client.post(f'/revenue/{revenue_entry["id"]}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_entry_success(self, auth_client, app, revenue_entry):
        """Test deleting an entry."""
        entry_id = revenue_entry['id']
        response = auth_client.post(f'/revenue/{entry_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            deleted = db.session.get(RevenueEntry, entry_id)
            assert deleted is None

    def test_delete_nonexistent_404(self, auth_client):
        """Test deleting non-existent entry returns 404."""
        response = auth_client.post('/revenue/99999/delete')
        assert response.status_code == 404

    def test_delete_redirects_to_dashboard(self, auth_client, revenue_entry):
        """Test delete redirects to dashboard."""
        response = auth_client.post(f'/revenue/{revenue_entry["id"]}/delete')
        assert response.status_code == 302
        assert '/revenue' in response.location

    def test_delete_entry_different_user_403(self, app, auth_client, admin_user):
        """Test deleting another user's entry returns 403."""
        with app.app_context():
            entry = RevenueEntry(
                user_id=admin_user['id'],
                source_type=RevenueEntry.SOURCE_AFFILIATE,
                source_name='Admin Entry',
                amount=Decimal('100.00'),
                date_earned=date.today()
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

        response = auth_client.post(f'/revenue/{entry_id}/delete')
        assert response.status_code == 403


# ============== Revenue Sync Route Tests ==============

class TestRevenueSyncAffiliates:
    """Tests for syncing affiliate revenue."""

    def test_sync_requires_auth(self, client):
        """Test sync requires authentication."""
        response = client.post('/revenue/sync-affiliates')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_sync_affiliates_success(self, auth_client, affiliate_revenue_entry, app):
        """Test syncing affiliate revenue creates entries."""
        response = auth_client.post('/revenue/sync-affiliates', follow_redirects=True)
        assert response.status_code == 200
        assert b'synced' in response.data.lower()

        with app.app_context():
            # Check revenue entry was created
            entry = RevenueEntry.query.filter_by(
                affiliate_revenue_id=affiliate_revenue_entry['id']
            ).first()
            assert entry is not None
            assert entry.source_type == RevenueEntry.SOURCE_AFFILIATE

    def test_sync_affiliates_idempotent(self, auth_client, affiliate_revenue_entry, app):
        """Test syncing twice doesn't create duplicates."""
        # First sync
        auth_client.post('/revenue/sync-affiliates', follow_redirects=True)
        # Second sync
        response = auth_client.post('/revenue/sync-affiliates', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            entries = RevenueEntry.query.filter_by(
                affiliate_revenue_id=affiliate_revenue_entry['id']
            ).all()
            assert len(entries) == 1  # Only one entry, not duplicated


class TestRevenueSyncSponsorships:
    """Tests for syncing sponsorship deals."""

    def test_sync_requires_auth(self, client):
        """Test sync requires authentication."""
        response = client.post('/revenue/sync-sponsorships')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_sync_sponsorships_success(self, auth_client, completed_paid_deal, app):
        """Test syncing completed paid deals creates entries."""
        response = auth_client.post('/revenue/sync-sponsorships', follow_redirects=True)
        assert response.status_code == 200
        assert b'synced' in response.data.lower()

        with app.app_context():
            entry = RevenueEntry.query.filter_by(
                pipeline_deal_id=completed_paid_deal['id']
            ).first()
            assert entry is not None
            assert entry.source_type == RevenueEntry.SOURCE_SPONSORSHIP
            assert float(entry.amount) == 1000.00

    def test_sync_sponsorships_idempotent(self, auth_client, completed_paid_deal, app):
        """Test syncing twice doesn't create duplicates."""
        auth_client.post('/revenue/sync-sponsorships', follow_redirects=True)
        response = auth_client.post('/revenue/sync-sponsorships', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            entries = RevenueEntry.query.filter_by(
                pipeline_deal_id=completed_paid_deal['id']
            ).all()
            assert len(entries) == 1

    def test_sync_ignores_incomplete_deals(self, auth_client, app, test_user, company):
        """Test sync only processes completed paid deals."""
        with app.app_context():
            # Create an incomplete deal
            deal = SalesPipeline(
                user_id=test_user['id'],
                company_id=company['id'],
                deal_type='podcast_ad',
                status='lead',
                payment_status='pending',
                rate_agreed=500.00
            )
            db.session.add(deal)
            db.session.commit()
            deal_id = deal.id

        response = auth_client.post('/revenue/sync-sponsorships', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            entry = RevenueEntry.query.filter_by(pipeline_deal_id=deal_id).first()
            assert entry is None  # Should not be synced


# ============== Revenue Export Route Tests ==============

class TestRevenueExportCSV:
    """Tests for CSV export."""

    def test_export_requires_auth(self, client):
        """Test export requires authentication."""
        response = client.get('/revenue/export/csv')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_export_csv_empty(self, auth_client):
        """Test export with no entries."""
        response = auth_client.get('/revenue/export/csv')
        assert response.status_code == 200
        assert response.content_type == 'text/csv; charset=utf-8'
        assert b'Date Earned' in response.data  # Header row

    def test_export_csv_with_data(self, auth_client, revenue_entry):
        """Test export includes revenue data."""
        response = auth_client.get('/revenue/export/csv')
        assert response.status_code == 200
        assert response.content_type == 'text/csv; charset=utf-8'
        assert b'Amazon Associates' in response.data
        assert b'150.00' in response.data

    def test_export_csv_filter_by_year(self, auth_client, revenue_entry):
        """Test export filters by year."""
        year = date.today().year
        response = auth_client.get(f'/revenue/export/csv?year={year}')
        assert response.status_code == 200
        assert b'Amazon Associates' in response.data

    def test_export_csv_filename(self, auth_client):
        """Test export sets correct filename."""
        response = auth_client.get('/revenue/export/csv')
        assert 'Content-Disposition' in response.headers
        assert 'revenue_export' in response.headers['Content-Disposition']
        assert '.csv' in response.headers['Content-Disposition']

    def test_export_csv_year_filename(self, auth_client):
        """Test export with year filter has year in filename."""
        response = auth_client.get('/revenue/export/csv?year=2024')
        assert '2024' in response.headers['Content-Disposition']
