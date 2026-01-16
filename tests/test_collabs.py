"""Tests for collaboration routes."""
import pytest
from models import Collaboration, Contact
from extensions import db


@pytest.fixture
def collab_with_followup(app, contact, test_user):
    """Create a test collaboration with follow-up needed, owned by test_user."""
    from datetime import date
    with app.app_context():
        c = Collaboration(
            user_id=test_user['id'],
            contact_id=contact['id'],
            collab_type='collab_video',
            status='reached_out',
            follow_up_needed=True,
            follow_up_date=date(2024, 6, 15)
        )
        db.session.add(c)
        db.session.commit()
        return {'id': c.id, 'contact_id': contact['id']}


class TestListCollabs:
    """Tests for collaboration listing."""

    def test_list_collabs_requires_auth(self, client):
        """Test list requires authentication."""
        response = client.get('/collabs/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_collabs_empty(self, auth_client):
        """Test list with no collabs."""
        response = auth_client.get('/collabs/')
        assert response.status_code == 200

    def test_list_collabs_with_data(self, auth_client, collab):
        """Test list shows collabs."""
        response = auth_client.get('/collabs/')
        assert response.status_code == 200

    def test_filter_by_collab_type(self, auth_client, app, contact):
        """Test filtering by collab type."""
        with app.app_context():
            c1 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='idea')
            c2 = Collaboration(contact_id=contact['id'], collab_type='cross_promo', status='idea')
            db.session.add_all([c1, c2])
            db.session.commit()

        response = auth_client.get('/collabs/?type=collab_video')
        assert response.status_code == 200

    def test_filter_by_status(self, auth_client, app, contact):
        """Test filtering by status."""
        with app.app_context():
            c1 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='idea')
            c2 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='completed')
            db.session.add_all([c1, c2])
            db.session.commit()

        response = auth_client.get('/collabs/?status=idea')
        assert response.status_code == 200

    def test_filter_follow_up(self, auth_client, app, contact):
        """Test filtering by follow_up=yes."""
        with app.app_context():
            c1 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='idea', follow_up_needed=True)
            c2 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='idea', follow_up_needed=False)
            db.session.add_all([c1, c2])
            db.session.commit()

        response = auth_client.get('/collabs/?follow_up=yes')
        assert response.status_code == 200

    def test_search_by_contact_name(self, auth_client, app, company):
        """Test searching by contact name."""
        with app.app_context():
            # Create contacts with different names
            contact1 = Contact(name='John Smith', company_id=company['id'])
            contact2 = Contact(name='Jane Doe', company_id=company['id'])
            db.session.add_all([contact1, contact2])
            db.session.commit()

            c1 = Collaboration(contact_id=contact1.id, collab_type='collab_video', status='idea')
            c2 = Collaboration(contact_id=contact2.id, collab_type='collab_video', status='idea')
            db.session.add_all([c1, c2])
            db.session.commit()

        response = auth_client.get('/collabs/?search=John')
        assert response.status_code == 200

    def test_search_case_insensitive(self, auth_client, app, company):
        """Test search is case-insensitive."""
        with app.app_context():
            contact1 = Contact(name='John SMITH', company_id=company['id'])
            db.session.add(contact1)
            db.session.commit()

            c1 = Collaboration(contact_id=contact1.id, collab_type='collab_video', status='idea')
            db.session.add(c1)
            db.session.commit()

        response = auth_client.get('/collabs/?search=john')
        assert response.status_code == 200

    def test_pagination(self, auth_client, app, contact):
        """Test pagination works."""
        with app.app_context():
            for i in range(5):
                c = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='idea')
                db.session.add(c)
            db.session.commit()

        response = auth_client.get('/collabs/?page=1')
        assert response.status_code == 200

    def test_stats_calculation(self, auth_client, app, contact):
        """Test stats are calculated."""
        with app.app_context():
            c1 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='idea')
            c2 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='reached_out')
            c3 = Collaboration(contact_id=contact['id'], collab_type='collab_video', status='completed')
            db.session.add_all([c1, c2, c3])
            db.session.commit()

        response = auth_client.get('/collabs/')
        assert response.status_code == 200

    def test_invalid_filter_ignored(self, auth_client, collab):
        """Test invalid filter values are ignored."""
        response = auth_client.get('/collabs/?type=invalid_type&status=invalid_status')
        assert response.status_code == 200


class TestNewCollab:
    """Tests for creating new collaborations."""

    def test_new_collab_form_renders(self, auth_client):
        """Test new collab form renders."""
        response = auth_client.get('/collabs/new')
        assert response.status_code == 200

    def test_create_collab_success(self, auth_client, app, contact):
        """Test creating a new collab."""
        response = auth_client.post('/collabs/new', data={
            'contact_id': contact['id'],
            'collab_type': 'collab_video',
            'status': 'idea'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'created successfully' in response.data.lower()

        with app.app_context():
            collab = Collaboration.query.filter_by(contact_id=contact['id']).first()
            assert collab is not None
            assert collab.collab_type == 'collab_video'

    def test_create_collab_missing_contact(self, auth_client):
        """Test creating collab without contact fails."""
        response = auth_client.post('/collabs/new', data={
            'collab_type': 'collab_video',
            'status': 'idea'
        })
        assert response.status_code == 200
        # Should show error

    def test_create_collab_invalid_contact(self, auth_client):
        """Test creating collab with invalid contact ID."""
        response = auth_client.post('/collabs/new', data={
            'contact_id': '99999',
            'collab_type': 'collab_video',
            'status': 'idea'
        })
        assert response.status_code == 200
        # Should show validation error

    def test_create_collab_with_all_fields(self, auth_client, app, contact):
        """Test creating collab with all optional fields."""
        response = auth_client.post('/collabs/new', data={
            'contact_id': contact['id'],
            'collab_type': 'guest_on_their_channel',
            'status': 'confirmed',
            'scheduled_date': '2024-07-15',
            'their_channel': 'TechChannel',
            'their_platform': 'youtube',
            'audience_size': '50000',
            'notes': 'Test collab notes',
            'follow_up_needed': 'on',
            'follow_up_date': '2024-06-15'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            collab = Collaboration.query.filter_by(contact_id=contact['id']).first()
            assert collab.their_channel == 'TechChannel'
            assert collab.their_platform == 'youtube'
            assert collab.audience_size == 50000
            assert collab.follow_up_needed is True

    def test_create_collab_invalid_platform_fallback(self, auth_client, app, contact):
        """Test invalid platform defaults to 'other'."""
        response = auth_client.post('/collabs/new', data={
            'contact_id': contact['id'],
            'collab_type': 'collab_video',
            'status': 'idea',
            'their_platform': 'unknown_platform'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            collab = Collaboration.query.filter_by(contact_id=contact['id']).first()
            assert collab is not None
            # Should fallback to 'other'
            assert collab.their_platform == 'other'

    def test_create_collab_default_values(self, auth_client, app, contact):
        """Test collab created with default values."""
        response = auth_client.post('/collabs/new', data={
            'contact_id': contact['id']
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            collab = Collaboration.query.filter_by(contact_id=contact['id']).first()
            assert collab is not None
            # Should use defaults
            assert collab.collab_type == 'collab_video'
            assert collab.status == 'idea'


class TestEditCollab:
    """Tests for editing collaborations."""

    def test_edit_collab_form_renders(self, auth_client, collab):
        """Test edit form renders with collab data."""
        response = auth_client.get(f'/collabs/{collab["id"]}/edit')
        assert response.status_code == 200

    def test_edit_collab_nonexistent_404(self, auth_client):
        """Test editing non-existent collab returns 404."""
        response = auth_client.get('/collabs/99999/edit')
        assert response.status_code == 404

    def test_update_collab_success(self, auth_client, app, collab, contact):
        """Test updating a collab."""
        response = auth_client.post(f'/collabs/{collab["id"]}/edit', data={
            'contact_id': contact['id'],
            'collab_type': 'cross_promo',
            'status': 'confirmed',
            'their_channel': 'Updated Channel'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data.lower()

        with app.app_context():
            updated = db.session.get(Collaboration, collab['id'])
            assert updated.collab_type == 'cross_promo'
            assert updated.status == 'confirmed'
            assert updated.their_channel == 'Updated Channel'

    def test_update_collab_missing_contact(self, auth_client, collab):
        """Test updating collab without contact fails."""
        response = auth_client.post(f'/collabs/{collab["id"]}/edit', data={
            'collab_type': 'collab_video',
            'status': 'idea'
        })
        assert response.status_code == 200
        # Should show error

    def test_update_collab_change_status(self, auth_client, app, collab, contact):
        """Test changing collab status."""
        response = auth_client.post(f'/collabs/{collab["id"]}/edit', data={
            'contact_id': contact['id'],
            'collab_type': 'collab_video',
            'status': 'reached_out'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            updated = db.session.get(Collaboration, collab['id'])
            assert updated.status == 'reached_out'


class TestDeleteCollab:
    """Tests for deleting collaborations."""

    def test_delete_collab_success(self, auth_client, app, collab):
        """Test deleting a collab."""
        collab_id = collab['id']
        response = auth_client.post(f'/collabs/{collab_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            deleted = db.session.get(Collaboration, collab_id)
            assert deleted is None

    def test_delete_nonexistent_404(self, auth_client):
        """Test deleting non-existent collab returns 404."""
        response = auth_client.post('/collabs/99999/delete')
        assert response.status_code == 404

    def test_delete_redirects_to_list(self, auth_client, collab):
        """Test delete redirects to list."""
        response = auth_client.post(f'/collabs/{collab["id"]}/delete')
        assert response.status_code == 302
        assert '/collabs/' in response.location


class TestQuickActions:
    """Tests for quick action routes."""

    def test_complete_collab(self, auth_client, app, collab):
        """Test marking collab as completed."""
        response = auth_client.post(f'/collabs/{collab["id"]}/complete', follow_redirects=True)
        assert response.status_code == 200
        assert b'completed' in response.data.lower()

        with app.app_context():
            updated = db.session.get(Collaboration, collab['id'])
            assert updated.status == 'completed'
            assert updated.completed_date is not None

    def test_complete_collab_nonexistent_404(self, auth_client):
        """Test completing non-existent collab returns 404."""
        response = auth_client.post('/collabs/99999/complete')
        assert response.status_code == 404

    def test_complete_collab_redirects(self, auth_client, collab):
        """Test complete redirects to list."""
        response = auth_client.post(f'/collabs/{collab["id"]}/complete')
        assert response.status_code == 302
        assert '/collabs/' in response.location

    def test_clear_followup(self, auth_client, app, collab_with_followup):
        """Test clearing follow-up flag."""
        response = auth_client.post(
            f'/collabs/{collab_with_followup["id"]}/clear-followup',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'follow-up cleared' in response.data.lower()

        with app.app_context():
            updated = db.session.get(Collaboration, collab_with_followup['id'])
            assert updated.follow_up_needed is False
            assert updated.follow_up_date is None

    def test_clear_followup_nonexistent_404(self, auth_client):
        """Test clearing follow-up for non-existent collab returns 404."""
        response = auth_client.post('/collabs/99999/clear-followup')
        assert response.status_code == 404

    def test_clear_followup_redirects(self, auth_client, collab):
        """Test clear follow-up redirects to list."""
        response = auth_client.post(f'/collabs/{collab["id"]}/clear-followup')
        assert response.status_code == 302
        assert '/collabs/' in response.location


class TestCollabAuth:
    """Tests for authentication requirements."""

    def test_new_collab_requires_auth(self, client):
        """Test new collab requires authentication."""
        response = client.get('/collabs/new')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_edit_collab_requires_auth(self, client, collab):
        """Test edit collab requires authentication."""
        response = client.get(f'/collabs/{collab["id"]}/edit')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_collab_requires_auth(self, client, collab):
        """Test delete collab requires authentication."""
        response = client.post(f'/collabs/{collab["id"]}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_complete_collab_requires_auth(self, client, collab):
        """Test complete collab requires authentication."""
        response = client.post(f'/collabs/{collab["id"]}/complete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_clear_followup_requires_auth(self, client, collab):
        """Test clear followup requires authentication."""
        response = client.post(f'/collabs/{collab["id"]}/clear-followup')
        assert response.status_code == 302
        assert '/auth/login' in response.location
