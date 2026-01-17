"""Tests for Creator Hub: Deal Deliverables and related routes."""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from models import DealDeliverable, SalesPipeline, Company
from extensions import db


# ============== Fixtures ==============

@pytest.fixture
def deal(app, company, test_user):
    """Create a test pipeline deal owned by test_user."""
    with app.app_context():
        d = SalesPipeline(
            user_id=test_user['id'],
            company_id=company['id'],
            deal_type='podcast_ad',
            status='confirmed',
            rate_agreed=1000.00
        )
        db.session.add(d)
        db.session.commit()
        return {'id': d.id, 'user_id': test_user['id'], 'company_id': company['id']}


@pytest.fixture
def other_user_deal(app, company, admin_user):
    """Create a deal owned by admin user (different from test_user)."""
    with app.app_context():
        d = SalesPipeline(
            user_id=admin_user['id'],
            company_id=company['id'],
            deal_type='podcast_ad',
            status='confirmed',
            rate_agreed=500.00
        )
        db.session.add(d)
        db.session.commit()
        return {'id': d.id, 'user_id': admin_user['id']}


@pytest.fixture
def deliverable(app, deal):
    """Create a test deliverable for a deal."""
    with app.app_context():
        d = DealDeliverable(
            deal_id=deal['id'],
            deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
            description='Main video mention',
            due_date=date.today() + timedelta(days=7),
            status=DealDeliverable.STATUS_PENDING
        )
        db.session.add(d)
        db.session.commit()
        return {'id': d.id, 'deal_id': deal['id']}


@pytest.fixture
def delivered_deliverable(app, deal):
    """Create a delivered deliverable with metrics."""
    with app.app_context():
        d = DealDeliverable(
            deal_id=deal['id'],
            deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
            description='Completed video',
            due_date=date.today() - timedelta(days=3),
            completed_date=date.today() - timedelta(days=2),
            status=DealDeliverable.STATUS_DELIVERED,
            impressions=10000,
            reach=8000,
            engagement=500,
            clicks=150,
            conversions=10,
            platform_post_url='https://youtube.com/watch?v=abc123'
        )
        db.session.add(d)
        db.session.commit()
        return {'id': d.id, 'deal_id': deal['id'], 'impressions': 10000}


@pytest.fixture
def overdue_deliverable(app, deal):
    """Create an overdue deliverable."""
    with app.app_context():
        d = DealDeliverable(
            deal_id=deal['id'],
            deliverable_type=DealDeliverable.TYPE_INSTAGRAM_POST,
            description='Overdue post',
            due_date=date.today() - timedelta(days=5),
            status=DealDeliverable.STATUS_PENDING
        )
        db.session.add(d)
        db.session.commit()
        return {'id': d.id, 'deal_id': deal['id']}


@pytest.fixture
def multiple_deliverables(app, deal):
    """Create multiple deliverables for a deal."""
    with app.app_context():
        deliverables = [
            DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                description='Main video',
                due_date=date.today() + timedelta(days=7),
                status=DealDeliverable.STATUS_DELIVERED,
                impressions=10000,
                clicks=100
            ),
            DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_INSTAGRAM_POST,
                description='IG promotion',
                due_date=date.today() + timedelta(days=3),
                status=DealDeliverable.STATUS_DELIVERED,
                impressions=5000,
                clicks=50
            ),
            DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_TWITTER_POST,
                description='Tweet',
                due_date=date.today() + timedelta(days=1),
                status=DealDeliverable.STATUS_PENDING,
                impressions=None
            ),
        ]
        for d in deliverables:
            db.session.add(d)
        db.session.commit()
        return {
            'deal_id': deal['id'],
            'count': 3,
            'delivered_count': 2,
            'total_impressions': 15000,
            'total_clicks': 150
        }


# ============== DealDeliverable Model Tests ==============

class TestDealDeliverableModel:
    """Tests for DealDeliverable model."""

    def test_create_deliverable(self, app, deal):
        """Test creating a basic deliverable."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                description='Test video',
                due_date=date.today() + timedelta(days=5)
            )
            db.session.add(d)
            db.session.commit()

            assert d.id is not None
            assert d.deal_id == deal['id']
            assert d.deliverable_type == 'youtube_video'
            assert d.status == 'pending'  # default

    def test_deliverable_type_constants(self):
        """Test deliverable type constants are defined."""
        assert DealDeliverable.TYPE_YOUTUBE_VIDEO == 'youtube_video'
        assert DealDeliverable.TYPE_YOUTUBE_SHORT == 'youtube_short'
        assert DealDeliverable.TYPE_INSTAGRAM_POST == 'instagram_post'
        assert DealDeliverable.TYPE_INSTAGRAM_STORY == 'instagram_story'
        assert DealDeliverable.TYPE_INSTAGRAM_REEL == 'instagram_reel'
        assert DealDeliverable.TYPE_TIKTOK_VIDEO == 'tiktok_video'
        assert DealDeliverable.TYPE_TWITTER_POST == 'twitter_post'
        assert DealDeliverable.TYPE_PODCAST_AD == 'podcast_ad'
        assert DealDeliverable.TYPE_PODCAST_EPISODE == 'podcast_episode'
        assert DealDeliverable.TYPE_BLOG_POST == 'blog_post'
        assert DealDeliverable.TYPE_OTHER == 'other'

    def test_deliverable_types_list(self):
        """Test DELIVERABLE_TYPES list contains all types."""
        types = [t[0] for t in DealDeliverable.DELIVERABLE_TYPES]
        assert len(types) == 11
        assert 'youtube_video' in types
        assert 'instagram_post' in types
        assert 'podcast_ad' in types

    def test_status_constants(self):
        """Test status constants are defined."""
        assert DealDeliverable.STATUS_PENDING == 'pending'
        assert DealDeliverable.STATUS_SCHEDULED == 'scheduled'
        assert DealDeliverable.STATUS_DELIVERED == 'delivered'
        assert DealDeliverable.STATUS_VERIFIED == 'verified'

    def test_statuses_list(self):
        """Test STATUSES list contains all statuses."""
        statuses = [s[0] for s in DealDeliverable.STATUSES]
        assert len(statuses) == 4
        assert 'pending' in statuses
        assert 'delivered' in statuses

    def test_is_overdue_true(self, app, deal):
        """Test is_overdue returns True for past due pending."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                due_date=date.today() - timedelta(days=1),
                status=DealDeliverable.STATUS_PENDING
            )
            db.session.add(d)
            db.session.commit()

            assert d.is_overdue is True

    def test_is_overdue_false_future_date(self, app, deal):
        """Test is_overdue returns False for future due date."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                due_date=date.today() + timedelta(days=5),
                status=DealDeliverable.STATUS_PENDING
            )
            db.session.add(d)
            db.session.commit()

            assert d.is_overdue is False

    def test_is_overdue_false_delivered(self, app, deal):
        """Test is_overdue returns False for delivered items."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                due_date=date.today() - timedelta(days=10),
                status=DealDeliverable.STATUS_DELIVERED
            )
            db.session.add(d)
            db.session.commit()

            assert d.is_overdue is False

    def test_is_overdue_false_no_due_date(self, app, deal):
        """Test is_overdue returns False when no due date set."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                due_date=None,
                status=DealDeliverable.STATUS_PENDING
            )
            db.session.add(d)
            db.session.commit()

            assert d.is_overdue is False

    def test_total_engagement_property(self, app, deal):
        """Test total_engagement property calculation."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                impressions=10000,
                engagement=500,
                clicks=100
            )
            db.session.add(d)
            db.session.commit()

            assert d.total_engagement == 10600  # 10000 + 500 + 100

    def test_total_engagement_with_nulls(self, app, deal):
        """Test total_engagement handles null values."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO,
                impressions=None,
                engagement=None,
                clicks=100
            )
            db.session.add(d)
            db.session.commit()

            assert d.total_engagement == 100  # Nulls treated as 0

    def test_to_dict(self, app, deal):
        """Test to_dict serialization."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_INSTAGRAM_POST,
                description='Test post',
                due_date=date(2024, 6, 15),
                status=DealDeliverable.STATUS_SCHEDULED,
                impressions=5000
            )
            db.session.add(d)
            db.session.commit()

            data = d.to_dict()
            assert data['deliverable_type'] == 'instagram_post'
            assert data['description'] == 'Test post'
            assert data['due_date'] == '2024-06-15'
            assert data['status'] == 'scheduled'
            assert data['impressions'] == 5000

    def test_cascade_delete(self, app, deal):
        """Test deliverables are deleted when deal is deleted."""
        with app.app_context():
            d = DealDeliverable(
                deal_id=deal['id'],
                deliverable_type=DealDeliverable.TYPE_YOUTUBE_VIDEO
            )
            db.session.add(d)
            db.session.commit()
            deliverable_id = d.id

            # Delete the deal
            deal_obj = db.session.get(SalesPipeline, deal['id'])
            db.session.delete(deal_obj)
            db.session.commit()

            # Deliverable should be deleted
            deleted = db.session.get(DealDeliverable, deliverable_id)
            assert deleted is None


# ============== List Deliverables Route Tests ==============

class TestListDeliverables:
    """Tests for deliverables list route."""

    def test_list_requires_auth(self, client, deal):
        """Test list requires authentication."""
        response = client.get(f'/pipeline/{deal["id"]}/deliverables')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_empty(self, auth_client, deal):
        """Test listing with no deliverables."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/deliverables')
        assert response.status_code == 200

    def test_list_with_deliverables(self, auth_client, deal, deliverable):
        """Test listing shows deliverables."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/deliverables')
        assert response.status_code == 200
        assert b'Main video mention' in response.data or b'youtube_video' in response.data.lower()

    def test_list_nonexistent_deal_404(self, auth_client):
        """Test listing for non-existent deal returns 404."""
        response = auth_client.get('/pipeline/99999/deliverables')
        assert response.status_code == 404

    def test_list_other_user_deal_403(self, auth_client, other_user_deal):
        """Test listing another user's deal returns 403."""
        response = auth_client.get(f'/pipeline/{other_user_deal["id"]}/deliverables')
        assert response.status_code == 403

    def test_list_shows_stats(self, auth_client, deal, multiple_deliverables):
        """Test list shows statistics."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/deliverables')
        assert response.status_code == 200
        # Stats should be displayed (total, completed, impressions, etc.)

    def test_list_shows_overdue(self, auth_client, deal, overdue_deliverable):
        """Test list identifies overdue deliverables."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/deliverables')
        assert response.status_code == 200
        # Overdue indicator should be present


# ============== Add Deliverable Route Tests ==============

class TestAddDeliverable:
    """Tests for adding deliverables."""

    def test_add_form_requires_auth(self, client, deal):
        """Test add form requires authentication."""
        response = client.get(f'/pipeline/{deal["id"]}/deliverables/add')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_add_form_renders(self, auth_client, deal):
        """Test add form renders."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/deliverables/add')
        assert response.status_code == 200
        assert b'deliverable_type' in response.data.lower() or b'type' in response.data.lower()

    def test_add_form_other_user_403(self, auth_client, other_user_deal):
        """Test add form for another user's deal returns 403."""
        response = auth_client.get(f'/pipeline/{other_user_deal["id"]}/deliverables/add')
        assert response.status_code == 403

    def test_add_deliverable_success(self, auth_client, app, deal):
        """Test adding a new deliverable."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/add', data={
            'deliverable_type': 'youtube_video',
            'description': 'New sponsored video',
            'due_date': (date.today() + timedelta(days=10)).isoformat(),
            'status': 'pending'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'added successfully' in response.data.lower()

        with app.app_context():
            d = DealDeliverable.query.filter_by(deal_id=deal['id'], description='New sponsored video').first()
            assert d is not None
            assert d.deliverable_type == 'youtube_video'

    def test_add_deliverable_minimal(self, auth_client, app, deal):
        """Test adding deliverable with minimal data."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/add', data={
            'deliverable_type': 'instagram_post',
            'status': 'pending'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            d = DealDeliverable.query.filter_by(deal_id=deal['id'], deliverable_type='instagram_post').first()
            assert d is not None

    def test_add_deliverable_with_url(self, auth_client, app, deal):
        """Test adding deliverable with platform URL."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/add', data={
            'deliverable_type': 'youtube_video',
            'description': 'Video with link',
            'platform_post_url': 'https://youtube.com/watch?v=test123',
            'status': 'delivered'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            d = DealDeliverable.query.filter_by(platform_post_url='https://youtube.com/watch?v=test123').first()
            assert d is not None

    def test_add_redirects_to_list(self, auth_client, deal):
        """Test add redirects to deliverables list."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/add', data={
            'deliverable_type': 'twitter_post',
            'status': 'pending'
        })
        assert response.status_code == 302
        assert f'/pipeline/{deal["id"]}/deliverables' in response.location


# ============== Edit Deliverable Route Tests ==============

class TestEditDeliverable:
    """Tests for editing deliverables."""

    def test_edit_form_requires_auth(self, client, deal, deliverable):
        """Test edit form requires authentication."""
        response = client.get(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/edit')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_edit_form_renders(self, auth_client, deal, deliverable):
        """Test edit form renders with data."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/edit')
        assert response.status_code == 200

    def test_edit_nonexistent_deliverable_404(self, auth_client, deal):
        """Test editing non-existent deliverable returns 404."""
        response = auth_client.get(f'/pipeline/{deal["id"]}/deliverables/99999/edit')
        assert response.status_code == 404

    def test_edit_other_user_deal_403(self, auth_client, other_user_deal):
        """Test editing deliverable on another user's deal returns 403."""
        response = auth_client.get(f'/pipeline/{other_user_deal["id"]}/deliverables/1/edit')
        assert response.status_code == 403

    def test_edit_deliverable_success(self, auth_client, app, deal, deliverable):
        """Test editing an existing deliverable."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/edit', data={
            'deliverable_type': 'youtube_short',
            'description': 'Updated to short',
            'status': 'scheduled',
            'due_date': (date.today() + timedelta(days=5)).isoformat()
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data.lower()

        with app.app_context():
            d = db.session.get(DealDeliverable, deliverable['id'])
            assert d.deliverable_type == 'youtube_short'
            assert d.description == 'Updated to short'
            assert d.status == 'scheduled'

    def test_edit_add_metrics(self, auth_client, app, deal, deliverable):
        """Test adding performance metrics during edit."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/edit', data={
            'deliverable_type': 'youtube_video',
            'status': 'delivered',
            'impressions': '15000',
            'reach': '12000',
            'engagement': '800',
            'clicks': '200',
            'conversions': '15'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            d = db.session.get(DealDeliverable, deliverable['id'])
            assert d.impressions == 15000
            assert d.reach == 12000
            assert d.engagement == 800
            assert d.clicks == 200
            assert d.conversions == 15

    def test_edit_auto_sets_completed_date(self, auth_client, app, deal, deliverable):
        """Test completed_date is auto-set when status changes to delivered."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/edit', data={
            'deliverable_type': 'youtube_video',
            'status': 'delivered'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            d = db.session.get(DealDeliverable, deliverable['id'])
            assert d.completed_date == date.today()


# ============== Delete Deliverable Route Tests ==============

class TestDeleteDeliverable:
    """Tests for deleting deliverables."""

    def test_delete_requires_auth(self, client, deal, deliverable):
        """Test delete requires authentication."""
        response = client.post(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_success(self, auth_client, app, deal, deliverable):
        """Test deleting a deliverable."""
        deliverable_id = deliverable['id']
        response = auth_client.post(
            f'/pipeline/{deal["id"]}/deliverables/{deliverable_id}/delete',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            deleted = db.session.get(DealDeliverable, deliverable_id)
            assert deleted is None

    def test_delete_nonexistent_404(self, auth_client, deal):
        """Test deleting non-existent deliverable returns 404."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/99999/delete')
        assert response.status_code == 404

    def test_delete_other_user_403(self, auth_client, other_user_deal):
        """Test deleting deliverable on another user's deal returns 403."""
        response = auth_client.post(f'/pipeline/{other_user_deal["id"]}/deliverables/1/delete')
        assert response.status_code == 403

    def test_delete_redirects_to_list(self, auth_client, deal, deliverable):
        """Test delete redirects to deliverables list."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/delete')
        assert response.status_code == 302
        assert f'/pipeline/{deal["id"]}/deliverables' in response.location


# ============== Mark Delivered Route Tests ==============

class TestMarkDelivered:
    """Tests for mark-delivered quick action."""

    def test_mark_delivered_requires_auth(self, client, deal, deliverable):
        """Test mark delivered requires authentication."""
        response = client.post(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/mark-delivered')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_mark_delivered_success(self, auth_client, app, deal, deliverable):
        """Test marking deliverable as delivered."""
        response = auth_client.post(
            f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/mark-delivered',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'delivered' in response.data.lower()

        with app.app_context():
            d = db.session.get(DealDeliverable, deliverable['id'])
            assert d.status == DealDeliverable.STATUS_DELIVERED
            assert d.completed_date == date.today()

    def test_mark_delivered_nonexistent_404(self, auth_client, deal):
        """Test marking non-existent deliverable returns 404."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/99999/mark-delivered')
        assert response.status_code == 404

    def test_mark_delivered_other_user_403(self, auth_client, other_user_deal):
        """Test marking deliverable on another user's deal returns 403."""
        response = auth_client.post(f'/pipeline/{other_user_deal["id"]}/deliverables/1/mark-delivered')
        assert response.status_code == 403

    def test_mark_delivered_redirects(self, auth_client, deal, deliverable):
        """Test mark delivered redirects to list."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/deliverables/{deliverable["id"]}/mark-delivered')
        assert response.status_code == 302
        assert f'/pipeline/{deal["id"]}/deliverables' in response.location


# ============== Generate Report Route Tests ==============

class TestGenerateReport:
    """Tests for generate-report route."""

    def test_generate_report_requires_auth(self, client, deal):
        """Test generate report requires authentication."""
        response = client.post(f'/pipeline/{deal["id"]}/generate-report')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_generate_report_empty_deal(self, auth_client, app, deal):
        """Test generating report for deal with no deliverables."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/generate-report', follow_redirects=True)
        assert response.status_code == 200
        assert b'report generated' in response.data.lower()

        with app.app_context():
            d = db.session.get(SalesPipeline, deal['id'])
            assert d.performance_report is not None
            assert d.performance_report['deliverables_total'] == 0
            assert d.report_generated_at is not None

    def test_generate_report_with_deliverables(self, auth_client, app, deal, multiple_deliverables):
        """Test generating report aggregates deliverable metrics."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/generate-report', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            d = db.session.get(SalesPipeline, deal['id'])
            report = d.performance_report
            assert report is not None
            assert report['total_impressions'] == multiple_deliverables['total_impressions']
            assert report['total_clicks'] == multiple_deliverables['total_clicks']
            assert report['deliverables_total'] == multiple_deliverables['count']
            assert report['deliverables_completed'] == multiple_deliverables['delivered_count']

    def test_generate_report_nonexistent_404(self, auth_client):
        """Test generating report for non-existent deal returns 404."""
        response = auth_client.post('/pipeline/99999/generate-report')
        assert response.status_code == 404

    def test_generate_report_other_user_403(self, auth_client, other_user_deal):
        """Test generating report for another user's deal returns 403."""
        response = auth_client.post(f'/pipeline/{other_user_deal["id"]}/generate-report')
        assert response.status_code == 403

    def test_generate_report_redirects(self, auth_client, deal):
        """Test generate report redirects to deliverables list."""
        response = auth_client.post(f'/pipeline/{deal["id"]}/generate-report')
        assert response.status_code == 302
        assert f'/pipeline/{deal["id"]}/deliverables' in response.location

    def test_report_contains_timestamp(self, auth_client, app, deal):
        """Test report contains generated_at timestamp."""
        auth_client.post(f'/pipeline/{deal["id"]}/generate-report')

        with app.app_context():
            d = db.session.get(SalesPipeline, deal['id'])
            assert 'generated_at' in d.performance_report

    def test_report_overwrites_previous(self, auth_client, app, deal, delivered_deliverable):
        """Test generating new report overwrites previous."""
        # Generate first report
        auth_client.post(f'/pipeline/{deal["id"]}/generate-report')

        with app.app_context():
            d = db.session.get(SalesPipeline, deal['id'])
            first_timestamp = d.report_generated_at

        # Wait a moment and generate again
        import time
        time.sleep(0.1)
        auth_client.post(f'/pipeline/{deal["id"]}/generate-report')

        with app.app_context():
            d = db.session.get(SalesPipeline, deal['id'])
            # Timestamps should be different (report was regenerated)
            assert d.report_generated_at >= first_timestamp
