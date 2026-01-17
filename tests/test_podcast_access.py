"""Tests for podcast access control utilities.

This module tests all functions in utils/podcast_access.py which is
SECURITY_SENSITIVE - handles authorization for multi-user podcast access.
"""
import pytest
from flask import g
from models import Podcast, PodcastMember, User
from extensions import db
from utils.podcast_access import (
    get_user_podcasts,
    get_user_role,
    user_has_podcast_access,
    user_is_podcast_admin,
    get_podcast_or_404,
    add_podcast_member,
    update_member_role,
    remove_podcast_member,
    can_delete_podcast,
)


class TestGetUserPodcasts:
    """Tests for get_user_podcasts function."""

    def test_returns_empty_for_unauthenticated(self, app, client):
        """Test returns empty list when no user_id and not authenticated."""
        # Access via route that uses get_user_podcasts indirectly
        # or pass explicit user_id=0 which won't match any user
        with app.app_context():
            result = get_user_podcasts(user_id=0)
            assert result == []

    def test_returns_empty_for_user_with_no_podcasts(self, app, test_user):
        """Test returns empty list for user with no podcast memberships."""
        with app.app_context():
            result = get_user_podcasts(user_id=test_user['id'])
            assert result == []

    def test_returns_podcasts_user_is_member_of(self, app, test_user):
        """Test returns podcasts where user has membership."""
        with app.app_context():
            # Create podcast and add user as member
            p = Podcast(name='My Podcast', slug='my-podcast', created_by=test_user['id'])
            db.session.add(p)
            db.session.flush()
            member = PodcastMember(podcast_id=p.id, user_id=test_user['id'], role='admin')
            db.session.add(member)
            db.session.commit()

            result = get_user_podcasts(user_id=test_user['id'])
            assert len(result) == 1
            assert result[0].name == 'My Podcast'

    def test_excludes_inactive_podcasts(self, app, test_user):
        """Test inactive podcasts are excluded from results."""
        with app.app_context():
            # Create active and inactive podcasts
            p1 = Podcast(name='Active', slug='active', created_by=test_user['id'], is_active=True)
            p2 = Podcast(name='Inactive', slug='inactive', created_by=test_user['id'], is_active=False)
            db.session.add_all([p1, p2])
            db.session.flush()

            # Add user as member of both
            m1 = PodcastMember(podcast_id=p1.id, user_id=test_user['id'], role='admin')
            m2 = PodcastMember(podcast_id=p2.id, user_id=test_user['id'], role='admin')
            db.session.add_all([m1, m2])
            db.session.commit()

            result = get_user_podcasts(user_id=test_user['id'])
            assert len(result) == 1
            assert result[0].name == 'Active'

    def test_returns_multiple_podcasts_sorted_by_name(self, app, test_user):
        """Test multiple podcasts are returned sorted by name."""
        with app.app_context():
            p1 = Podcast(name='Zebra Cast', slug='zebra', created_by=test_user['id'])
            p2 = Podcast(name='Alpha Cast', slug='alpha', created_by=test_user['id'])
            db.session.add_all([p1, p2])
            db.session.flush()

            m1 = PodcastMember(podcast_id=p1.id, user_id=test_user['id'], role='admin')
            m2 = PodcastMember(podcast_id=p2.id, user_id=test_user['id'], role='contributor')
            db.session.add_all([m1, m2])
            db.session.commit()

            result = get_user_podcasts(user_id=test_user['id'])
            assert len(result) == 2
            assert result[0].name == 'Alpha Cast'
            assert result[1].name == 'Zebra Cast'


class TestGetUserRole:
    """Tests for get_user_role function."""

    def test_returns_none_for_non_member(self, app, test_user, podcast):
        """Test returns None for user who is not a member."""
        with app.app_context():
            # Create a different user
            other = User(email='other@test.com', is_approved=True)
            other.set_password('TestPass123!')
            db.session.add(other)
            db.session.commit()

            role = get_user_role(podcast['id'], user_id=other.id)
            assert role is None

    def test_returns_admin_for_admin_member(self, app, test_user, podcast):
        """Test returns 'admin' for admin member."""
        with app.app_context():
            role = get_user_role(podcast['id'], user_id=test_user['id'])
            assert role == 'admin'

    def test_returns_contributor_for_contributor_member(self, app, test_user, podcast):
        """Test returns 'contributor' for contributor member."""
        with app.app_context():
            # Add a contributor
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('TestPass123!')
            db.session.add(contrib)
            db.session.flush()

            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()

            role = get_user_role(podcast['id'], user_id=contrib.id)
            assert role == 'contributor'

    def test_returns_none_for_nonexistent_podcast(self, app, test_user):
        """Test returns None for non-existent podcast ID."""
        with app.app_context():
            role = get_user_role(99999, user_id=test_user['id'])
            assert role is None


class TestUserHasPodcastAccess:
    """Tests for user_has_podcast_access function."""

    def test_returns_true_for_admin(self, app, test_user, podcast):
        """Test returns True for admin member."""
        with app.app_context():
            assert user_has_podcast_access(podcast['id'], user_id=test_user['id']) is True

    def test_returns_true_for_contributor(self, app, test_user, podcast):
        """Test returns True for contributor member."""
        with app.app_context():
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('TestPass123!')
            db.session.add(contrib)
            db.session.flush()

            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()

            assert user_has_podcast_access(podcast['id'], user_id=contrib.id) is True

    def test_returns_false_for_non_member(self, app, test_user, podcast):
        """Test returns False for non-member."""
        with app.app_context():
            other = User(email='other@test.com', is_approved=True)
            other.set_password('TestPass123!')
            db.session.add(other)
            db.session.commit()

            assert user_has_podcast_access(podcast['id'], user_id=other.id) is False


class TestUserIsPodcastAdmin:
    """Tests for user_is_podcast_admin function."""

    def test_returns_true_for_admin(self, app, test_user, podcast):
        """Test returns True for admin member."""
        with app.app_context():
            assert user_is_podcast_admin(podcast['id'], user_id=test_user['id']) is True

    def test_returns_false_for_contributor(self, app, test_user, podcast):
        """Test returns False for contributor member."""
        with app.app_context():
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('TestPass123!')
            db.session.add(contrib)
            db.session.flush()

            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()

            assert user_is_podcast_admin(podcast['id'], user_id=contrib.id) is False

    def test_returns_false_for_non_member(self, app, test_user, podcast):
        """Test returns False for non-member."""
        with app.app_context():
            other = User(email='other@test.com', is_approved=True)
            other.set_password('TestPass123!')
            db.session.add(other)
            db.session.commit()

            assert user_is_podcast_admin(podcast['id'], user_id=other.id) is False


class TestGetPodcastOr404:
    """Tests for get_podcast_or_404 function."""

    def test_returns_podcast_when_exists(self, app, podcast):
        """Test returns podcast object when it exists."""
        with app.app_context():
            result = get_podcast_or_404(podcast['id'])
            assert result.id == podcast['id']
            assert result.name == podcast['name']

    def test_raises_404_for_nonexistent(self, app):
        """Test raises 404 for non-existent podcast ID."""
        with app.app_context():
            from werkzeug.exceptions import NotFound
            with pytest.raises(NotFound):
                get_podcast_or_404(99999)


class TestAddPodcastMember:
    """Tests for add_podcast_member function."""

    def test_adds_member_with_default_role(self, app, test_user, podcast):
        """Test adds member with default contributor role."""
        with app.app_context():
            new_user = User(email='new@test.com', is_approved=True)
            new_user.set_password('TestPass123!')
            db.session.add(new_user)
            db.session.commit()

            # Pass explicit added_by to avoid needing current_user
            member = add_podcast_member(podcast['id'], new_user.id, added_by=test_user['id'])
            db.session.commit()

            assert member is not None
            assert member.role == 'contributor'
            assert member.podcast_id == podcast['id']
            assert member.user_id == new_user.id

    def test_adds_member_as_admin(self, app, test_user, podcast):
        """Test adds member with admin role when specified."""
        with app.app_context():
            new_user = User(email='new@test.com', is_approved=True)
            new_user.set_password('TestPass123!')
            db.session.add(new_user)
            db.session.commit()

            # Pass explicit added_by to avoid needing current_user
            member = add_podcast_member(podcast['id'], new_user.id, role='admin', added_by=test_user['id'])
            db.session.commit()

            assert member is not None
            assert member.role == 'admin'

    def test_returns_none_for_existing_member(self, app, test_user, podcast):
        """Test returns None if user is already a member."""
        with app.app_context():
            # test_user is already a member from fixture
            result = add_podcast_member(podcast['id'], test_user['id'], added_by=test_user['id'])
            assert result is None

    def test_raises_for_invalid_role(self, app, test_user, podcast):
        """Test raises ValueError for invalid role."""
        with app.app_context():
            new_user = User(email='new@test.com', is_approved=True)
            new_user.set_password('TestPass123!')
            db.session.add(new_user)
            db.session.commit()

            with pytest.raises(ValueError) as exc:
                add_podcast_member(podcast['id'], new_user.id, role='superadmin')
            assert "Invalid role" in str(exc.value)


class TestUpdateMemberRole:
    """Tests for update_member_role function."""

    def test_updates_contributor_to_admin(self, app, test_user, podcast):
        """Test can promote contributor to admin."""
        with app.app_context():
            # Add a contributor
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('TestPass123!')
            db.session.add(contrib)
            db.session.flush()
            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()

            result = update_member_role(podcast['id'], contrib.id, 'admin')
            db.session.commit()

            assert result is not None
            assert result.role == 'admin'

    def test_updates_admin_to_contributor_when_other_admins_exist(self, app, test_user, podcast):
        """Test can demote admin when other admins exist."""
        with app.app_context():
            # Add another admin
            admin2 = User(email='admin2@test.com', is_approved=True)
            admin2.set_password('TestPass123!')
            db.session.add(admin2)
            db.session.flush()
            member = PodcastMember(podcast_id=podcast['id'], user_id=admin2.id, role='admin')
            db.session.add(member)
            db.session.commit()

            # Now demote test_user
            result = update_member_role(podcast['id'], test_user['id'], 'contributor')
            db.session.commit()

            assert result is not None
            assert result.role == 'contributor'

    def test_raises_when_removing_last_admin(self, app, test_user, podcast):
        """Test raises ValueError when trying to demote the last admin."""
        with app.app_context():
            # test_user is the only admin
            with pytest.raises(ValueError) as exc:
                update_member_role(podcast['id'], test_user['id'], 'contributor')
            assert "last admin" in str(exc.value).lower()

    def test_returns_none_for_nonexistent_member(self, app, podcast):
        """Test returns None for non-existent member."""
        with app.app_context():
            result = update_member_role(podcast['id'], 99999, 'admin')
            assert result is None

    def test_raises_for_invalid_role(self, app, test_user, podcast):
        """Test raises ValueError for invalid role."""
        with app.app_context():
            with pytest.raises(ValueError) as exc:
                update_member_role(podcast['id'], test_user['id'], 'owner')
            assert "Invalid role" in str(exc.value)


class TestRemovePodcastMember:
    """Tests for remove_podcast_member function."""

    def test_removes_contributor(self, app, test_user, podcast):
        """Test can remove contributor member."""
        with app.app_context():
            # Add a contributor
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('TestPass123!')
            db.session.add(contrib)
            db.session.flush()
            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()
            contrib_id = contrib.id

            result = remove_podcast_member(podcast['id'], contrib_id)
            db.session.commit()

            assert result is True
            # Verify member is gone
            remaining = PodcastMember.query.filter_by(
                podcast_id=podcast['id'], user_id=contrib_id
            ).first()
            assert remaining is None

    def test_removes_admin_when_other_admins_exist(self, app, test_user, podcast):
        """Test can remove admin when other admins exist."""
        with app.app_context():
            # Add another admin
            admin2 = User(email='admin2@test.com', is_approved=True)
            admin2.set_password('TestPass123!')
            db.session.add(admin2)
            db.session.flush()
            member = PodcastMember(podcast_id=podcast['id'], user_id=admin2.id, role='admin')
            db.session.add(member)
            db.session.commit()

            # Remove test_user
            result = remove_podcast_member(podcast['id'], test_user['id'])
            db.session.commit()

            assert result is True

    def test_raises_when_removing_last_admin(self, app, test_user, podcast):
        """Test raises ValueError when trying to remove the last admin."""
        with app.app_context():
            with pytest.raises(ValueError) as exc:
                remove_podcast_member(podcast['id'], test_user['id'])
            assert "last admin" in str(exc.value).lower()

    def test_returns_false_for_nonexistent_member(self, app, podcast):
        """Test returns False for non-existent member."""
        with app.app_context():
            result = remove_podcast_member(podcast['id'], 99999)
            assert result is False


class TestCanDeletePodcast:
    """Tests for can_delete_podcast function."""

    def test_admin_can_delete(self, app, test_user, podcast):
        """Test admin can delete podcast."""
        with app.app_context():
            assert can_delete_podcast(podcast['id'], user_id=test_user['id']) is True

    def test_contributor_cannot_delete(self, app, test_user, podcast):
        """Test contributor cannot delete podcast."""
        with app.app_context():
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('TestPass123!')
            db.session.add(contrib)
            db.session.flush()
            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()

            assert can_delete_podcast(podcast['id'], user_id=contrib.id) is False

    def test_non_member_cannot_delete(self, app, podcast):
        """Test non-member cannot delete podcast."""
        with app.app_context():
            other = User(email='other@test.com', is_approved=True)
            other.set_password('TestPass123!')
            db.session.add(other)
            db.session.commit()

            assert can_delete_podcast(podcast['id'], user_id=other.id) is False
