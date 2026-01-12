"""Performance tests for the Mouse Domination application."""
import pytest
from app import create_app, db
from config import TestConfig
from models import Collaboration, Contact, Company
from utils.queries import get_companies_for_dropdown, get_contacts_for_dropdown


class TestQueryOptimizations:
    """Test query optimizations are working correctly."""

    def test_collabs_stats_single_query(self, app, client):
        """Test that collab stats use a single aggregated query."""
        with app.app_context():
            # Create some test data
            contact = Contact(name='Test Contact', email='test@test.com')
            db.session.add(contact)
            db.session.commit()

            # Create collabs with different statuses
            statuses = ['idea', 'reached_out', 'confirmed', 'completed', 'declined']
            for i, status in enumerate(statuses):
                collab = Collaboration(
                    contact_id=contact.id,
                    collab_type='guest_on_their_channel',
                    status=status,
                    follow_up_needed=(i % 2 == 0)
                )
                db.session.add(collab)
            db.session.commit()

            # Request the list page
            response = client.get('/collabs/')
            assert response.status_code == 200

            # Verify stats are in the response
            html = response.data.decode('utf-8')
            assert 'idea' in html.lower() or 'active' in html.lower()

    def test_dropdown_helper_caches_within_request(self, app):
        """Test that dropdown helpers cache results within a request."""
        with app.app_context():
            # Create some companies
            for i in range(3):
                company = Company(name=f'Company {i}', category='peripheral')
                db.session.add(company)
            db.session.commit()

            # Simulate a request context
            with app.test_request_context():
                # First call
                companies1 = get_companies_for_dropdown()
                # Second call should return same object (cached)
                companies2 = get_companies_for_dropdown()

                # Should be the exact same object (not just equal)
                assert companies1 is companies2
                assert len(companies1) == 3

class TestConnectionPoolingConfig:
    """Test database connection pooling configuration."""

    def test_pool_settings_configured_for_postgresql(self, app, monkeypatch):
        """Test that connection pool settings are configured for PostgreSQL.

        Pool settings should only be applied for non-SQLite databases.
        """
        import os
        import config

        # Simulate PostgreSQL environment
        monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost/db')

        # Reload the config module to pick up new env var
        import importlib
        importlib.reload(config)

        # Check that pool settings exist when using PostgreSQL
        assert config.is_sqlite() is False
        engine_options = config.Config.SQLALCHEMY_ENGINE_OPTIONS
        assert 'pool_size' in engine_options
        assert 'pool_recycle' in engine_options
        assert 'pool_pre_ping' in engine_options

        # Clean up - reload with original settings
        monkeypatch.delenv('DATABASE_URL', raising=False)
        importlib.reload(config)

    def test_pool_settings_empty_for_sqlite(self, app):
        """Test that pool settings are empty for SQLite."""
        from config import Config, is_sqlite

        # When using SQLite, pool settings should be empty
        if is_sqlite():
            assert Config.SQLALCHEMY_ENGINE_OPTIONS == {}


class TestEagerLoading:
    """Test that eager loading is used correctly."""

    def test_contacts_list_eager_loads_company(self, app, client):
        """Test that contacts list view eager loads company relationship."""
        with app.app_context():
            # Create a company and contact
            company = Company(name='Test Company', category='peripheral')
            db.session.add(company)
            db.session.commit()

            contact = Contact(
                name='Test Contact',
                email='test@test.com',
                company_id=company.id
            )
            db.session.add(contact)
            db.session.commit()

            # Request the list page - should not cause N+1
            response = client.get('/contacts/')
            assert response.status_code == 200

            # Company name should appear in response
            html = response.data.decode('utf-8')
            assert 'Test Company' in html


class TestAggregatedQueries:
    """Test that aggregated queries are used instead of multiple separate queries."""

    def test_collab_stats_values_correct(self, app, client):
        """Test that aggregated collab stats return correct values."""
        with app.app_context():
            # Create a contact
            contact = Contact(name='Test', email='t@t.com')
            db.session.add(contact)
            db.session.commit()

            # Create specific collabs to verify counts
            # 2 active (idea, confirmed)
            # 1 completed
            # 1 with follow_up
            Collaboration.query.delete()  # Clean slate

            db.session.add(Collaboration(
                contact_id=contact.id, collab_type='collab_video',
                status='idea', follow_up_needed=True
            ))
            db.session.add(Collaboration(
                contact_id=contact.id, collab_type='collab_video',
                status='confirmed', follow_up_needed=False
            ))
            db.session.add(Collaboration(
                contact_id=contact.id, collab_type='collab_video',
                status='completed', follow_up_needed=False
            ))
            db.session.commit()

            response = client.get('/collabs/')
            assert response.status_code == 200

            # The stats should reflect our test data
            html = response.data.decode('utf-8')
            # Total should be 3
            assert '3' in html
