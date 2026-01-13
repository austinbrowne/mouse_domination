"""Tests for admin routes."""
import pytest
from models import User
from extensions import db


class TestAdminRequired:
    """Tests for admin_required decorator."""

    def test_admin_required_not_logged_in(self, client):
        """Test admin route redirects to login when not authenticated."""
        response = client.get('/admin/users')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_admin_required_not_admin(self, auth_client):
        """Test non-admin user gets 403."""
        response = auth_client.get('/admin/users')
        assert response.status_code == 403

    def test_admin_required_admin(self, admin_client):
        """Test admin user can access admin routes."""
        response = admin_client.get('/admin/users')
        assert response.status_code == 200


class TestListUsers:
    """Tests for user list route."""

    def test_list_users_shows_pending(self, admin_client, app, unapproved_user):
        """Test pending users are shown in list."""
        response = admin_client.get('/admin/users')
        assert response.status_code == 200
        assert b'pending@example.com' in response.data

    def test_list_users_shows_approved(self, admin_client, app, test_user):
        """Test approved users are shown in list."""
        response = admin_client.get('/admin/users')
        assert response.status_code == 200
        # The test_user from fixture should be in approved list
        assert b'test@example.com' in response.data

    def test_list_users_empty_pending(self, admin_client, app):
        """Test list handles no pending users."""
        # Only admin user exists (created by fixture)
        response = admin_client.get('/admin/users')
        assert response.status_code == 200

    def test_list_users_requires_login(self, client):
        """Test list requires authentication."""
        response = client.get('/admin/users')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_users_requires_admin(self, auth_client):
        """Test list requires admin privileges."""
        response = auth_client.get('/admin/users')
        assert response.status_code == 403


class TestApproveUser:
    """Tests for user approval."""

    def test_approve_user_success(self, admin_client, app, unapproved_user):
        """Test approving a pending user."""
        response = admin_client.post(
            f'/admin/users/{unapproved_user["id"]}/approve',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'has been approved' in response.data

        with app.app_context():
            user = db.session.get(User, unapproved_user['id'])
            assert user.is_approved is True

    def test_approve_already_approved(self, admin_client, app, test_user):
        """Test approving already approved user shows info message."""
        response = admin_client.post(
            f'/admin/users/{test_user["id"]}/approve',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'already approved' in response.data

    def test_approve_nonexistent_404(self, admin_client):
        """Test approving non-existent user returns 404."""
        response = admin_client.post('/admin/users/99999/approve')
        assert response.status_code == 404

    def test_approve_requires_login(self, client, unapproved_user):
        """Test approve requires authentication."""
        response = client.post(f'/admin/users/{unapproved_user["id"]}/approve')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_approve_requires_admin(self, auth_client, unapproved_user):
        """Test approve requires admin privileges."""
        response = auth_client.post(f'/admin/users/{unapproved_user["id"]}/approve')
        assert response.status_code == 403

    def test_approve_redirects_to_list(self, admin_client, unapproved_user):
        """Test approve redirects to user list."""
        response = admin_client.post(
            f'/admin/users/{unapproved_user["id"]}/approve'
        )
        assert response.status_code == 302
        assert '/admin/users' in response.location


class TestRejectUser:
    """Tests for user rejection/deletion."""

    def test_reject_user_success(self, admin_client, app, unapproved_user):
        """Test rejecting/deleting a user."""
        user_id = unapproved_user['id']
        response = admin_client.post(
            f'/admin/users/{user_id}/reject',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'has been rejected' in response.data

        with app.app_context():
            user = db.session.get(User, user_id)
            assert user is None

    def test_reject_self_blocked(self, admin_client, admin_user):
        """Test admin cannot delete themselves."""
        response = admin_client.post(
            f'/admin/users/{admin_user["id"]}/reject',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'cannot delete yourself' in response.data.lower()

    def test_reject_admin_blocked(self, admin_client, app):
        """Test cannot delete admin users."""
        # Create another admin user
        with app.app_context():
            other_admin = User(
                email='other_admin@example.com',
                name='Other Admin',
                is_approved=True,
                is_admin=True
            )
            other_admin.set_password('TestPassword123!')
            db.session.add(other_admin)
            db.session.commit()
            other_admin_id = other_admin.id

        response = admin_client.post(
            f'/admin/users/{other_admin_id}/reject',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'cannot delete admin' in response.data.lower()

    def test_reject_nonexistent_404(self, admin_client):
        """Test rejecting non-existent user returns 404."""
        response = admin_client.post('/admin/users/99999/reject')
        assert response.status_code == 404

    def test_reject_requires_login(self, client, unapproved_user):
        """Test reject requires authentication."""
        response = client.post(f'/admin/users/{unapproved_user["id"]}/reject')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_reject_requires_admin(self, auth_client, unapproved_user):
        """Test reject requires admin privileges."""
        response = auth_client.post(f'/admin/users/{unapproved_user["id"]}/reject')
        assert response.status_code == 403

    def test_reject_redirects_to_list(self, admin_client, unapproved_user):
        """Test reject redirects to user list."""
        response = admin_client.post(
            f'/admin/users/{unapproved_user["id"]}/reject'
        )
        assert response.status_code == 302
        assert '/admin/users' in response.location


class TestToggleAdmin:
    """Tests for toggling admin status."""

    def test_toggle_admin_grant(self, admin_client, app, test_user):
        """Test granting admin privileges."""
        response = admin_client.post(
            f'/admin/users/{test_user["id"]}/toggle-admin',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'granted' in response.data

        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.is_admin is True

    def test_toggle_admin_revoke(self, admin_client, app):
        """Test revoking admin privileges."""
        # Create an admin user to revoke
        with app.app_context():
            admin_to_revoke = User(
                email='revoke_admin@example.com',
                name='Revoke Admin',
                is_approved=True,
                is_admin=True
            )
            admin_to_revoke.set_password('TestPassword123!')
            db.session.add(admin_to_revoke)
            db.session.commit()
            user_id = admin_to_revoke.id

        response = admin_client.post(
            f'/admin/users/{user_id}/toggle-admin',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'revoked' in response.data

        with app.app_context():
            user = db.session.get(User, user_id)
            assert user.is_admin is False

    def test_toggle_self_blocked(self, admin_client, admin_user):
        """Test admin cannot modify their own admin status."""
        response = admin_client.post(
            f'/admin/users/{admin_user["id"]}/toggle-admin',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'cannot modify your own' in response.data.lower()

    def test_toggle_nonexistent_404(self, admin_client):
        """Test toggling non-existent user returns 404."""
        response = admin_client.post('/admin/users/99999/toggle-admin')
        assert response.status_code == 404

    def test_toggle_requires_login(self, client, test_user):
        """Test toggle requires authentication."""
        response = client.post(f'/admin/users/{test_user["id"]}/toggle-admin')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_toggle_requires_admin(self, auth_client, test_user):
        """Test toggle requires admin privileges."""
        # auth_client is logged in as test_user (non-admin)
        # So we need another user to try toggling
        response = auth_client.post(f'/admin/users/{test_user["id"]}/toggle-admin')
        assert response.status_code == 403

    def test_toggle_redirects_to_list(self, admin_client, test_user):
        """Test toggle redirects to user list."""
        response = admin_client.post(
            f'/admin/users/{test_user["id"]}/toggle-admin'
        )
        assert response.status_code == 302
        assert '/admin/users' in response.location
