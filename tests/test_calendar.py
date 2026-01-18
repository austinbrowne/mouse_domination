"""Tests for the Calendar feature."""
import pytest
from datetime import date, timedelta
from flask import url_for
from app import db
from models import EpisodeGuide, Inventory, SalesPipeline, Collaboration, Company, Contact, Podcast


class TestCalendarModels:
    """Test that new date fields exist on models."""

    def test_episode_guide_scheduled_date_field(self, app):
        """EpisodeGuide has scheduled_date field."""
        with app.app_context():
            guide = EpisodeGuide(title='Test Episode')
            guide.scheduled_date = date.today()
            db.session.add(guide)
            db.session.commit()
            assert guide.scheduled_date == date.today()

    def test_episode_guide_scheduled_date_nullable(self, app):
        """EpisodeGuide.scheduled_date can be None."""
        with app.app_context():
            guide = EpisodeGuide(title='Test Episode')
            db.session.add(guide)
            db.session.commit()
            assert guide.scheduled_date is None

    def test_inventory_return_by_date_field(self, app, test_user):
        """Inventory has return_by_date field."""
        with app.app_context():
            item = Inventory(
                product_name='Test Mouse',
                user_id=test_user['id']
            )
            item.return_by_date = date.today()
            db.session.add(item)
            db.session.commit()
            assert item.return_by_date == date.today()

    def test_inventory_return_by_date_nullable(self, app, test_user):
        """Inventory.return_by_date can be None."""
        with app.app_context():
            item = Inventory(
                product_name='Test Mouse',
                user_id=test_user['id']
            )
            db.session.add(item)
            db.session.commit()
            assert item.return_by_date is None

    def test_sales_pipeline_deliverable_date_field(self, app):
        """SalesPipeline has deliverable_date field."""
        with app.app_context():
            company = Company(name='Test Company')
            db.session.add(company)
            db.session.commit()

            deal = SalesPipeline(
                company_id=company.id,
                deal_type='sponsored_video'
            )
            deal.deliverable_date = date.today()
            db.session.add(deal)
            db.session.commit()
            assert deal.deliverable_date == date.today()

    def test_sales_pipeline_deliverable_date_nullable(self, app):
        """SalesPipeline.deliverable_date can be None."""
        with app.app_context():
            company = Company(name='Test Company 2')
            db.session.add(company)
            db.session.commit()

            deal = SalesPipeline(
                company_id=company.id,
                deal_type='sponsored_video'
            )
            db.session.add(deal)
            db.session.commit()
            assert deal.deliverable_date is None


class TestCalendarRoutes:
    """Test calendar routes."""

    def test_calendar_view_requires_login(self, client):
        """GET /calendar requires authentication."""
        response = client.get('/calendar/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_calendar_view_authenticated(self, auth_client):
        """GET /calendar returns 200 when authenticated."""
        response = auth_client.get('/calendar/')
        assert response.status_code == 200
        assert b'Calendar' in response.data

    def test_calendar_api_requires_login(self, client):
        """GET /calendar/api/events requires authentication."""
        response = client.get('/calendar/api/events')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_calendar_api_returns_json(self, auth_client):
        """GET /calendar/api/events returns JSON."""
        response = auth_client.get('/calendar/api/events')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        data = response.get_json()
        assert 'events' in data
        assert isinstance(data['events'], list)

    def test_calendar_api_filters_by_date_range(self, app, auth_client):
        """API filters events by start and end dates."""
        with app.app_context():
            guide = EpisodeGuide(
                title='Test Episode',
                scheduled_date=date(2025, 6, 15)
            )
            db.session.add(guide)
            db.session.commit()

        response = auth_client.get('/calendar/api/events?start=2025-06-01&end=2025-06-30')
        assert response.status_code == 200
        data = response.get_json()

        episode_events = [e for e in data['events'] if e['type'] == 'episode']
        assert len(episode_events) == 1
        assert '2025-06-15' in episode_events[0]['date']

    def test_calendar_api_excludes_outside_range(self, app, auth_client):
        """API excludes events outside date range."""
        with app.app_context():
            guide = EpisodeGuide(
                title='July Episode',
                scheduled_date=date(2025, 7, 15)
            )
            db.session.add(guide)
            db.session.commit()

        response = auth_client.get('/calendar/api/events?start=2025-06-01&end=2025-06-30')
        data = response.get_json()

        episode_events = [e for e in data['events'] if 'July Episode' in e.get('title', '')]
        assert len(episode_events) == 0

    def test_calendar_api_invalid_date_format(self, auth_client):
        """API returns error for invalid date format."""
        response = auth_client.get('/calendar/api/events?start=invalid&end=2025-06-30')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


class TestCalendarEventTypes:
    """Test that all event types are returned correctly."""

    def test_episode_events(self, app, auth_client):
        """Episode events are returned with correct format."""
        with app.app_context():
            guide = EpisodeGuide(
                title='Test Episode',
                scheduled_date=date.today()
            )
            db.session.add(guide)
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        episode_events = [e for e in data['events'] if e['type'] == 'episode']
        assert len(episode_events) == 1
        event = episode_events[0]
        assert event['title'].startswith('Episode:')
        assert event['color'] == '#3b82f6'  # Blue
        assert '/podcasts/' in event['url'] or '#' in event['url']

    def test_inventory_deadline_events(self, app, auth_client, test_user):
        """Inventory deadline events are returned."""
        with app.app_context():
            item = Inventory(
                product_name='Deadline Mouse',
                deadline=date.today(),
                status='in_queue',
                user_id=test_user['id']
            )
            db.session.add(item)
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        deadline_events = [e for e in data['events'] if e['type'] == 'inventory_deadline']
        assert len(deadline_events) == 1
        assert deadline_events[0]['color'] == '#ef4444'  # Red

    def test_inventory_deadline_hidden_for_reviewed(self, app, auth_client, test_user):
        """Inventory deadline is hidden for reviewed items."""
        with app.app_context():
            item = Inventory(
                product_name='Reviewed Mouse',
                deadline=date.today(),
                status='reviewed',
                user_id=test_user['id']
            )
            db.session.add(item)
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        # Should not find deadline events for reviewed items
        deadline_events = [e for e in data['events'] if 'Reviewed Mouse' in e.get('title', '')]
        assert len(deadline_events) == 0

    def test_inventory_return_events(self, app, auth_client, test_user):
        """Inventory return_by_date events are returned."""
        with app.app_context():
            item = Inventory(
                product_name='Loaner Mouse',
                return_by_date=date.today(),
                user_id=test_user['id']
            )
            db.session.add(item)
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        return_events = [e for e in data['events'] if e['type'] == 'inventory_return']
        assert len(return_events) == 1
        assert return_events[0]['color'] == '#f97316'  # Orange

    def test_pipeline_events(self, app, auth_client):
        """Pipeline events are returned with correct colors."""
        with app.app_context():
            company = Company(name='Pipeline Test Co')
            db.session.add(company)
            db.session.commit()

            deal = SalesPipeline(
                company_id=company.id,
                deal_type='sponsored_video',
                deadline=date.today(),
                deliverable_date=date.today() + timedelta(days=1),
                payment_date=date.today() + timedelta(days=7)
            )
            db.session.add(deal)
            db.session.commit()

        end_date = date.today() + timedelta(days=10)
        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={end_date}')
        data = response.get_json()

        # Check pipeline deadline
        deadline_events = [e for e in data['events'] if e['type'] == 'pipeline_deadline']
        assert len(deadline_events) == 1
        assert deadline_events[0]['color'] == '#22c55e'  # Green

        # Check deliverable
        deliverable_events = [e for e in data['events'] if e['type'] == 'pipeline_deliverable']
        assert len(deliverable_events) == 1
        assert deliverable_events[0]['color'] == '#14b8a6'  # Teal

        # Check payment
        payment_events = [e for e in data['events'] if e['type'] == 'pipeline_payment']
        assert len(payment_events) == 1
        assert payment_events[0]['color'] == '#8b5cf6'  # Purple

    def test_collab_events(self, app, auth_client):
        """Collaboration events are returned."""
        with app.app_context():
            contact = Contact(name='Collab Test Contact')
            db.session.add(contact)
            db.session.commit()

            collab = Collaboration(
                contact_id=contact.id,
                collab_type='review',
                scheduled_date=date.today()
            )
            db.session.add(collab)
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        collab_events = [e for e in data['events'] if e['type'] == 'collab']
        assert len(collab_events) == 1
        assert collab_events[0]['color'] == '#ec4899'  # Pink

    def test_follow_up_events(self, app, auth_client):
        """Follow-up events are returned."""
        with app.app_context():
            contact = Contact(name='Follow-up Test Contact')
            db.session.add(contact)
            db.session.commit()

            collab = Collaboration(
                contact_id=contact.id,
                collab_type='review',
                follow_up_date=date.today()
            )
            db.session.add(collab)
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        followup_events = [e for e in data['events'] if e['type'] == 'follow_up']
        assert len(followup_events) >= 1
        assert any(e['color'] == '#6b7280' for e in followup_events)  # Gray


class TestCalendarEventFormat:
    """Test that event format is correct."""

    def test_event_has_required_fields(self, app, auth_client):
        """Events have all required fields."""
        with app.app_context():
            guide = EpisodeGuide(
                title='Format Test',
                scheduled_date=date.today()
            )
            db.session.add(guide)
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        for event in data['events']:
            assert 'id' in event
            assert 'title' in event
            assert 'date' in event
            assert 'type' in event
            assert 'color' in event
            assert 'url' in event

    def test_event_urls_are_valid(self, app, auth_client, test_user):
        """Event URLs are valid route URLs."""
        with app.app_context():
            # Create podcast first so episode has valid URL
            podcast = Podcast(name='URL Test Podcast', slug='url-test-podcast', created_by=test_user['id'])
            db.session.add(podcast)
            db.session.flush()

            guide = EpisodeGuide(title='URL Test', scheduled_date=date.today(), podcast_id=podcast.id)
            item = Inventory(product_name='URL Mouse', deadline=date.today(), user_id=test_user['id'])

            db.session.add_all([guide, item])
            db.session.commit()

        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={date.today()}')
        data = response.get_json()

        for event in data['events']:
            # URLs should start with /
            assert event['url'].startswith('/')

    def test_events_sorted_by_date(self, app, auth_client):
        """Events are sorted by date."""
        with app.app_context():
            guide1 = EpisodeGuide(title='First', scheduled_date=date.today())
            guide2 = EpisodeGuide(title='Second', scheduled_date=date.today() + timedelta(days=2))
            guide3 = EpisodeGuide(title='Third', scheduled_date=date.today() + timedelta(days=1))

            db.session.add_all([guide1, guide2, guide3])
            db.session.commit()

        end_date = date.today() + timedelta(days=5)
        response = auth_client.get(f'/calendar/api/events?start={date.today()}&end={end_date}')
        data = response.get_json()

        dates = [e['date'] for e in data['events']]
        assert dates == sorted(dates)


class TestCalendarToDict:
    """Test that to_dict methods include new fields."""

    def test_episode_guide_to_dict_has_scheduled_date(self, app):
        """EpisodeGuide.to_dict() includes scheduled_date."""
        with app.app_context():
            guide = EpisodeGuide(
                title='Dict Test',
                scheduled_date=date(2025, 1, 15)
            )
            db.session.add(guide)
            db.session.commit()

            data = guide.to_dict()
            assert 'scheduled_date' in data
            assert data['scheduled_date'] == '2025-01-15'

    def test_episode_guide_to_dict_scheduled_date_none(self, app):
        """EpisodeGuide.to_dict() handles None scheduled_date."""
        with app.app_context():
            guide = EpisodeGuide(title='None Date Test')
            db.session.add(guide)
            db.session.commit()

            data = guide.to_dict()
            assert 'scheduled_date' in data
            assert data['scheduled_date'] is None

    def test_inventory_to_dict_has_return_by_date(self, app, test_user):
        """Inventory.to_dict() includes return_by_date."""
        with app.app_context():
            item = Inventory(
                product_name='Dict Mouse',
                return_by_date=date(2025, 2, 20),
                user_id=test_user['id']
            )
            db.session.add(item)
            db.session.commit()

            data = item.to_dict()
            assert 'return_by_date' in data
            assert data['return_by_date'] == '2025-02-20'

    def test_sales_pipeline_to_dict_has_deliverable_date(self, app):
        """SalesPipeline.to_dict() includes deliverable_date."""
        with app.app_context():
            company = Company(name='Dict Company')
            db.session.add(company)
            db.session.commit()

            deal = SalesPipeline(
                company_id=company.id,
                deal_type='sponsored_video',
                deliverable_date=date(2025, 3, 10)
            )
            db.session.add(deal)
            db.session.commit()

            data = deal.to_dict()
            assert 'deliverable_date' in data
            assert data['deliverable_date'] == '2025-03-10'
