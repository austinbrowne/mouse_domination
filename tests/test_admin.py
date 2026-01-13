"""Tests for admin routes."""
import pytest
from models import User, CustomOption
from extensions import db


class TestAdminIndex:
    """Tests for admin index/landing page."""

    def test_admin_index_requires_login(self, client):
        """Test admin index redirects to login when not authenticated."""
        response = client.get('/admin/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_admin_index_requires_admin(self, auth_client):
        """Test non-admin user gets 403."""
        response = auth_client.get('/admin/')
        assert response.status_code == 403

    def test_admin_index_success(self, admin_client):
        """Test admin can access admin index."""
        response = admin_client.get('/admin/')
        assert response.status_code == 200
        assert b'Admin Dashboard' in response.data

    def test_admin_index_shows_links(self, admin_client):
        """Test admin index shows links to sub-pages."""
        response = admin_client.get('/admin/')
        assert response.status_code == 200
        assert b'User Management' in response.data
        assert b'Custom Options' in response.data

    def test_admin_index_shows_pending_count(self, admin_client, app, unapproved_user):
        """Test admin index shows pending user count."""
        response = admin_client.get('/admin/')
        assert response.status_code == 200
        assert b'pending approval' in response.data


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


class TestListOptions:
    """Tests for custom options list route."""

    def test_list_options_requires_login(self, client):
        """Test list options redirects to login when not authenticated."""
        response = client.get('/admin/options')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_options_requires_admin(self, auth_client):
        """Test non-admin user gets 403."""
        response = auth_client.get('/admin/options')
        assert response.status_code == 403

    def test_list_options_success(self, admin_client):
        """Test admin can access options list."""
        response = admin_client.get('/admin/options')
        assert response.status_code == 200
        assert b'Custom Options' in response.data

    def test_list_options_shows_builtin(self, admin_client):
        """Test builtin options are displayed."""
        response = admin_client.get('/admin/options')
        assert response.status_code == 200
        # Should show builtin inventory categories
        assert b'Mouse' in response.data
        assert b'Keyboard' in response.data

    def test_list_options_shows_custom(self, admin_client, app, admin_user):
        """Test custom options are displayed."""
        # Create a custom option
        with app.app_context():
            option = CustomOption(
                option_type='inventory_category',
                value='flashlight',
                label='Flashlight',
                created_by=admin_user['id']
            )
            db.session.add(option)
            db.session.commit()

        response = admin_client.get('/admin/options')
        assert response.status_code == 200
        assert b'Flashlight' in response.data


class TestCreateOption:
    """Tests for creating custom options."""

    def test_create_option_requires_login(self, client):
        """Test create option redirects to login when not authenticated."""
        response = client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'test',
            'label': 'Test'
        })
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_create_option_requires_admin(self, auth_client):
        """Test non-admin user gets 403."""
        response = auth_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'test',
            'label': 'Test'
        })
        assert response.status_code == 403

    def test_create_option_success(self, admin_client, app):
        """Test admin can create custom option."""
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'flashlight',
            'label': 'Flashlight'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'added successfully' in response.data

        # Verify option was created
        with app.app_context():
            option = CustomOption.query.filter_by(value='flashlight').first()
            assert option is not None
            assert option.label == 'Flashlight'
            assert option.option_type == 'inventory_category'

    def test_create_option_normalizes_value(self, admin_client, app):
        """Test value is normalized to lowercase with underscores."""
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'My Custom Type',
            'label': 'My Custom Type'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            option = CustomOption.query.filter_by(value='my_custom_type').first()
            assert option is not None

    def test_create_option_invalid_type(self, admin_client):
        """Test invalid option type is rejected."""
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'invalid_type',
            'value': 'test',
            'label': 'Test'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Invalid option type' in response.data

    def test_create_option_empty_value(self, admin_client):
        """Test empty value is rejected."""
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': '',
            'label': 'Test'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'required' in response.data

    def test_create_option_empty_label(self, admin_client):
        """Test empty label is rejected."""
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'test',
            'label': ''
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'required' in response.data

    def test_create_option_builtin_conflict(self, admin_client):
        """Test cannot create option with value matching builtin."""
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'mouse',
            'label': 'Mouse'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'already a built-in' in response.data

    def test_create_option_duplicate(self, admin_client, app, admin_user):
        """Test cannot create duplicate option."""
        # Create first option
        with app.app_context():
            option = CustomOption(
                option_type='inventory_category',
                value='flashlight',
                label='Flashlight',
                created_by=admin_user['id']
            )
            db.session.add(option)
            db.session.commit()

        # Try to create duplicate
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'flashlight',
            'label': 'Another Flashlight'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'already exists' in response.data

    def test_create_option_redirects(self, admin_client):
        """Test create redirects to options list."""
        response = admin_client.post('/admin/options/new', data={
            'option_type': 'inventory_category',
            'value': 'test',
            'label': 'Test'
        })
        assert response.status_code == 302
        assert '/admin/options' in response.location


class TestDeleteOption:
    """Tests for deleting custom options."""

    def test_delete_option_requires_login(self, client, app, admin_user):
        """Test delete option redirects to login when not authenticated."""
        # Create option to delete
        with app.app_context():
            option = CustomOption(
                option_type='inventory_category',
                value='flashlight',
                label='Flashlight',
                created_by=admin_user['id']
            )
            db.session.add(option)
            db.session.commit()
            option_id = option.id

        response = client.post(f'/admin/options/{option_id}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_option_requires_admin(self, auth_client, app, admin_user):
        """Test non-admin user gets 403."""
        with app.app_context():
            option = CustomOption(
                option_type='inventory_category',
                value='flashlight',
                label='Flashlight',
                created_by=admin_user['id']
            )
            db.session.add(option)
            db.session.commit()
            option_id = option.id

        response = auth_client.post(f'/admin/options/{option_id}/delete')
        assert response.status_code == 403

    def test_delete_option_success(self, admin_client, app, admin_user):
        """Test admin can delete custom option."""
        with app.app_context():
            option = CustomOption(
                option_type='inventory_category',
                value='flashlight',
                label='Flashlight',
                created_by=admin_user['id']
            )
            db.session.add(option)
            db.session.commit()
            option_id = option.id

        response = admin_client.post(
            f'/admin/options/{option_id}/delete',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'deleted' in response.data

        # Verify option was deleted
        with app.app_context():
            option = db.session.get(CustomOption, option_id)
            assert option is None

    def test_delete_option_nonexistent_404(self, admin_client):
        """Test deleting non-existent option returns 404."""
        response = admin_client.post('/admin/options/99999/delete')
        assert response.status_code == 404

    def test_delete_option_redirects(self, admin_client, app, admin_user):
        """Test delete redirects to options list."""
        with app.app_context():
            option = CustomOption(
                option_type='inventory_category',
                value='flashlight',
                label='Flashlight',
                created_by=admin_user['id']
            )
            db.session.add(option)
            db.session.commit()
            option_id = option.id

        response = admin_client.post(f'/admin/options/{option_id}/delete')
        assert response.status_code == 302
        assert '/admin/options' in response.location
