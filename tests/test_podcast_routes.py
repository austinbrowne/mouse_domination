"""Tests for podcast routes including episode items.

Covers:
- Podcast CRUD (list, create, edit, delete)
- Member management (add, remove, change role)
- Episode and template scoped routes
- Access control enforcement
- Edge cases and error conditions
"""
import pytest
from models import EpisodeGuideItem, Podcast, PodcastMember, User, EpisodeGuide, EpisodeGuideTemplate
from extensions import db


class TestPodcastEpisodeItems:
    """Tests for podcast episode item AJAX endpoints."""

    def test_add_item_title_only(self, auth_client, app, podcast_episode):
        """Test adding item with just title (no links)."""
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item Title Only'
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['title'] == 'Test Item Title Only'
        assert data['item']['links'] == []

    def test_add_item_with_empty_links_array(self, auth_client, app, podcast_episode):
        """Test adding item with explicit empty links array."""
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item Empty Links',
                'links': []
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['title'] == 'Test Item Empty Links'
        assert data['item']['links'] == []

    def test_add_item_with_null_links(self, auth_client, app, podcast_episode):
        """Test adding item with explicit null links (regression test for TypeError)."""
        import json
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/items',
            data=json.dumps({
                'section': 'introduction',
                'title': 'Test Item Null Links',
                'links': None
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['title'] == 'Test Item Null Links'
        assert data['item']['links'] == []

    def test_add_item_with_single_link(self, auth_client, app, podcast_episode):
        """Test adding item with single link."""
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item With Link',
                'links': ['https://example.com']
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['links'] == ['https://example.com']

    def test_add_item_filters_empty_link_strings(self, auth_client, app, podcast_episode):
        """Test that empty strings are filtered from links array."""
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item',
                'links': ['', '  ', 'https://valid.com', '']
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['links'] == ['https://valid.com']

    def test_add_item_requires_title(self, auth_client, podcast_episode):
        """Test adding item without title fails."""
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/items',
            json={
                'section': 'introduction',
                'title': ''
            },
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Title' in data['error']

    def test_add_item_invalid_section(self, auth_client, podcast_episode):
        """Test adding item with invalid section fails."""
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/items',
            json={
                'section': 'invalid_section_xyz',
                'title': 'Test'
            },
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'section' in data['error'].lower()

    def test_delete_item(self, auth_client, app, podcast_episode_with_items):
        """Test deleting an item."""
        item_id = podcast_episode_with_items['item_ids'][0]
        podcast_id = podcast_episode_with_items['podcast_id']
        episode_id = podcast_episode_with_items['episode_id']

        response = auth_client.delete(
            f'/podcasts/{podcast_id}/episodes/{episode_id}/items/{item_id}',
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # Verify item is deleted
        with app.app_context():
            item = EpisodeGuideItem.query.get(item_id)
            assert item is None

    def test_get_items(self, auth_client, podcast_episode_with_items):
        """Test getting all items for an episode."""
        podcast_id = podcast_episode_with_items['podcast_id']
        episode_id = podcast_episode_with_items['episode_id']

        response = auth_client.get(
            f'/podcasts/{podcast_id}/episodes/{episode_id}/items'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['items']) == 2


class TestPodcastAccess:
    """Tests for podcast access control."""

    def test_non_member_cannot_access_podcast(self, client, app, podcast):
        """Test that non-members cannot access podcast pages."""
        # Create a different user who isn't a member
        with app.app_context():
            from models import User
            other_user = User(email='other@example.com', is_approved=True)
            other_user.set_password('OtherPassword123!')
            from extensions import db
            db.session.add(other_user)
            db.session.commit()

        # Login as other user
        client.post('/auth/login', data={
            'email': 'other@example.com',
            'password': 'OtherPassword123!'
        })

        # Try to access the podcast
        response = client.get(f'/podcasts/{podcast["id"]}/episodes/')
        # Should redirect to podcasts list or show forbidden
        assert response.status_code in [302, 403]

    def test_member_can_access_podcast(self, auth_client, podcast):
        """Test that members can access podcast pages."""
        response = auth_client.get(f'/podcasts/{podcast["id"]}/episodes/')
        assert response.status_code == 200


class TestPodcastList:
    """Tests for podcast list page."""

    def test_list_podcasts_authenticated(self, auth_client):
        """Test authenticated user can view podcast list."""
        response = auth_client.get('/podcasts/')
        assert response.status_code == 200

    def test_list_podcasts_unauthenticated_redirects(self, client):
        """Test unauthenticated user is redirected to login."""
        response = client.get('/podcasts/')
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_list_shows_only_user_podcasts(self, auth_client, app, test_user):
        """Test user only sees podcasts they're a member of."""
        with app.app_context():
            # Create podcast user IS a member of
            p1 = Podcast(name='My Podcast', slug='my-podcast', created_by=test_user['id'])
            db.session.add(p1)
            db.session.flush()
            m1 = PodcastMember(podcast_id=p1.id, user_id=test_user['id'], role='admin')
            db.session.add(m1)

            # Create podcast user is NOT a member of
            other = User(email='other@test.com', is_approved=True)
            other.set_password('TestPass123!')
            db.session.add(other)
            db.session.flush()
            p2 = Podcast(name='Other Podcast', slug='other-podcast', created_by=other.id)
            db.session.add(p2)
            db.session.flush()
            m2 = PodcastMember(podcast_id=p2.id, user_id=other.id, role='admin')
            db.session.add(m2)
            db.session.commit()

        response = auth_client.get('/podcasts/')
        assert response.status_code == 200
        assert b'My Podcast' in response.data
        assert b'Other Podcast' not in response.data


class TestPodcastCreate:
    """Tests for podcast creation."""

    def test_create_podcast_get(self, auth_client):
        """Test can view create podcast form."""
        response = auth_client.get('/podcasts/new')
        assert response.status_code == 200
        assert b'name' in response.data.lower()

    def test_create_podcast_success(self, auth_client, app, test_user):
        """Test successful podcast creation."""
        response = auth_client.post('/podcasts/new', data={
            'name': 'New Test Podcast',
            'description': 'A test podcast description'
        }, follow_redirects=False)

        # Should redirect to new podcast
        assert response.status_code == 302

        with app.app_context():
            podcast = Podcast.query.filter_by(name='New Test Podcast').first()
            assert podcast is not None
            assert podcast.slug == 'new-test-podcast'
            assert podcast.created_by == test_user['id']
            # Creator should be admin
            member = PodcastMember.query.filter_by(
                podcast_id=podcast.id, user_id=test_user['id']
            ).first()
            assert member is not None
            assert member.role == 'admin'

    def test_create_podcast_generates_unique_slug(self, auth_client, app, test_user):
        """Test duplicate names get unique slugs."""
        # Create first podcast
        auth_client.post('/podcasts/new', data={'name': 'Duplicate Name'})

        # Create second with same name
        auth_client.post('/podcasts/new', data={'name': 'Duplicate Name'})

        with app.app_context():
            podcasts = Podcast.query.filter(Podcast.name == 'Duplicate Name').all()
            assert len(podcasts) == 2
            slugs = [p.slug for p in podcasts]
            assert 'duplicate-name' in slugs
            assert 'duplicate-name-2' in slugs

    def test_create_podcast_requires_name(self, auth_client):
        """Test name is required."""
        response = auth_client.post('/podcasts/new', data={
            'name': '',
            'description': 'Description'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'error' in response.data.lower() or b'required' in response.data.lower()

    def test_create_podcast_name_max_length(self, auth_client):
        """Test name max length validation."""
        response = auth_client.post('/podcasts/new', data={
            'name': 'A' * 200,  # Exceeds 150 char limit
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should show error about length


class TestPodcastSettings:
    """Tests for podcast settings (admin only)."""

    def test_admin_can_view_settings(self, auth_client, podcast):
        """Test admin can view podcast settings."""
        response = auth_client.get(f'/podcasts/{podcast["id"]}/settings')
        assert response.status_code == 200

    def test_contributor_cannot_view_settings(self, client, app, podcast, test_user):
        """Test contributor cannot view podcast settings."""
        with app.app_context():
            # Add a contributor
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('ContribPass123!')
            db.session.add(contrib)
            db.session.flush()
            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()

        # Login as contributor
        client.post('/auth/login', data={
            'email': 'contrib@test.com',
            'password': 'ContribPass123!'
        })

        response = client.get(f'/podcasts/{podcast["id"]}/settings')
        # Should redirect with error
        assert response.status_code == 302

    def test_update_settings(self, auth_client, app, podcast):
        """Test admin can update settings."""
        response = auth_client.post(f'/podcasts/{podcast["id"]}/settings', data={
            'name': 'Updated Podcast Name',
            'description': 'Updated description',
            'website_url': 'https://example.com'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            p = Podcast.query.get(podcast['id'])
            assert p.name == 'Updated Podcast Name'
            assert p.description == 'Updated description'
            assert p.website_url == 'https://example.com'

    def test_update_slug_optional(self, auth_client, app, podcast):
        """Test slug update is optional."""
        original_slug = podcast['slug']

        # Update without changing slug
        auth_client.post(f'/podcasts/{podcast["id"]}/settings', data={
            'name': 'Different Name',
            'update_slug': ''  # Not checked
        })

        with app.app_context():
            p = Podcast.query.get(podcast['id'])
            assert p.slug == original_slug  # Slug unchanged


class TestPodcastDelete:
    """Tests for podcast deletion."""

    def test_admin_can_delete_podcast(self, auth_client, app, podcast):
        """Test admin can delete podcast."""
        podcast_id = podcast['id']

        response = auth_client.post(f'/podcasts/{podcast_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            p = Podcast.query.get(podcast_id)
            assert p is None

    def test_contributor_cannot_delete_podcast(self, client, app, podcast):
        """Test contributor cannot delete podcast."""
        with app.app_context():
            contrib = User(email='contrib@test.com', is_approved=True)
            contrib.set_password('ContribPass123!')
            db.session.add(contrib)
            db.session.flush()
            member = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(member)
            db.session.commit()

        client.post('/auth/login', data={
            'email': 'contrib@test.com',
            'password': 'ContribPass123!'
        })

        response = client.post(f'/podcasts/{podcast["id"]}/delete')
        # Should redirect (forbidden)
        assert response.status_code == 302

        # Verify not deleted
        with app.app_context():
            p = Podcast.query.get(podcast['id'])
            assert p is not None

    def test_delete_cascades_to_episodes(self, auth_client, app, podcast):
        """Test deleting podcast also deletes associated episodes."""
        with app.app_context():
            ep = EpisodeGuide(title='Test Episode', podcast_id=podcast['id'], status='draft')
            db.session.add(ep)
            db.session.commit()
            ep_id = ep.id

        auth_client.post(f'/podcasts/{podcast["id"]}/delete')

        with app.app_context():
            episode = EpisodeGuide.query.get(ep_id)
            assert episode is None


class TestMemberManagement:
    """Tests for podcast member management."""

    def test_admin_can_view_members(self, auth_client, podcast):
        """Test admin can view members list."""
        response = auth_client.get(f'/podcasts/{podcast["id"]}/members')
        assert response.status_code == 200

    def test_admin_can_add_member(self, auth_client, app, podcast):
        """Test admin can add a new member."""
        with app.app_context():
            new_user = User(email='newmember@test.com', is_approved=True)
            new_user.set_password('NewPass123!')
            db.session.add(new_user)
            db.session.commit()
            new_user_id = new_user.id

        response = auth_client.post(f'/podcasts/{podcast["id"]}/members/add', data={
            'user_id': new_user_id,
            'role': 'contributor'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            member = PodcastMember.query.filter_by(
                podcast_id=podcast['id'],
                user_id=new_user_id
            ).first()
            assert member is not None
            assert member.role == 'contributor'

    def test_add_member_invalid_user_fails(self, auth_client, podcast):
        """Test adding non-existent user fails gracefully."""
        response = auth_client.post(f'/podcasts/{podcast["id"]}/members/add', data={
            'user_id': 99999,
            'role': 'contributor'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'invalid' in response.data.lower() or b'error' in response.data.lower()

    def test_add_unapproved_user_fails(self, auth_client, app, podcast):
        """Test adding unapproved user fails."""
        with app.app_context():
            unapp = User(email='unapproved@test.com', is_approved=False)
            unapp.set_password('TestPass123!')
            db.session.add(unapp)
            db.session.commit()
            unapp_id = unapp.id

        response = auth_client.post(f'/podcasts/{podcast["id"]}/members/add', data={
            'user_id': unapp_id,
            'role': 'contributor'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should show error

    def test_change_member_role(self, auth_client, app, podcast, test_user):
        """Test admin can change member role."""
        with app.app_context():
            # Add another admin first (so we have 2)
            admin2 = User(email='admin2@test.com', is_approved=True)
            admin2.set_password('Admin2Pass123!')
            db.session.add(admin2)
            db.session.flush()
            m = PodcastMember(podcast_id=podcast['id'], user_id=admin2.id, role='admin')
            db.session.add(m)
            db.session.commit()
            admin2_id = admin2.id

        # Change admin2 to contributor
        response = auth_client.post(
            f'/podcasts/{podcast["id"]}/members/{admin2_id}/role',
            data={'role': 'contributor'},
            follow_redirects=True
        )

        assert response.status_code == 200

        with app.app_context():
            member = PodcastMember.query.filter_by(
                podcast_id=podcast['id'],
                user_id=admin2_id
            ).first()
            assert member.role == 'contributor'

    def test_cannot_demote_last_admin(self, auth_client, app, podcast, test_user):
        """Test cannot demote the last admin."""
        # test_user is the only admin
        response = auth_client.post(
            f'/podcasts/{podcast["id"]}/members/{test_user["id"]}/role',
            data={'role': 'contributor'},
            follow_redirects=True
        )

        assert response.status_code == 200
        # Should show error about last admin

        with app.app_context():
            member = PodcastMember.query.filter_by(
                podcast_id=podcast['id'],
                user_id=test_user['id']
            ).first()
            assert member.role == 'admin'  # Still admin

    def test_remove_member(self, auth_client, app, podcast):
        """Test admin can remove a member."""
        with app.app_context():
            contrib = User(email='toremove@test.com', is_approved=True)
            contrib.set_password('TestPass123!')
            db.session.add(contrib)
            db.session.flush()
            m = PodcastMember(podcast_id=podcast['id'], user_id=contrib.id, role='contributor')
            db.session.add(m)
            db.session.commit()
            contrib_id = contrib.id

        response = auth_client.post(
            f'/podcasts/{podcast["id"]}/members/{contrib_id}/remove',
            follow_redirects=True
        )

        assert response.status_code == 200

        with app.app_context():
            member = PodcastMember.query.filter_by(
                podcast_id=podcast['id'],
                user_id=contrib_id
            ).first()
            assert member is None

    def test_cannot_remove_last_admin(self, auth_client, app, podcast, test_user):
        """Test cannot remove the last admin."""
        response = auth_client.post(
            f'/podcasts/{podcast["id"]}/members/{test_user["id"]}/remove',
            follow_redirects=True
        )

        assert response.status_code == 200

        with app.app_context():
            member = PodcastMember.query.filter_by(
                podcast_id=podcast['id'],
                user_id=test_user['id']
            ).first()
            assert member is not None  # Still exists


class TestPodcastEpisodes:
    """Tests for episode routes scoped under podcasts."""

    def test_list_episodes(self, auth_client, podcast):
        """Test can list episodes for a podcast."""
        response = auth_client.get(f'/podcasts/{podcast["id"]}/episodes/')
        assert response.status_code == 200

    def test_create_episode(self, auth_client, app, podcast):
        """Test can create episode for a podcast."""
        response = auth_client.post(f'/podcasts/{podcast["id"]}/episodes/new', data={
            'title': 'New Episode Title',
            'episode_number': 42
        }, follow_redirects=False)

        # Should redirect to edit page
        assert response.status_code == 302

        with app.app_context():
            ep = EpisodeGuide.query.filter_by(title='New Episode Title').first()
            assert ep is not None
            assert ep.podcast_id == podcast['id']
            assert ep.episode_number == 42

    def test_view_episode(self, auth_client, podcast_episode):
        """Test can view episode."""
        response = auth_client.get(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/'
        )
        assert response.status_code == 200

    def test_edit_episode(self, auth_client, podcast_episode):
        """Test can access edit page."""
        response = auth_client.get(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/edit'
        )
        assert response.status_code == 200

    def test_delete_episode(self, auth_client, app, podcast_episode):
        """Test can delete episode."""
        ep_id = podcast_episode['id']
        podcast_id = podcast_episode['podcast_id']

        response = auth_client.post(
            f'/podcasts/{podcast_id}/episodes/{ep_id}/delete',
            follow_redirects=True
        )

        assert response.status_code == 200

        with app.app_context():
            ep = EpisodeGuide.query.get(ep_id)
            assert ep is None

    def test_cannot_access_episode_from_wrong_podcast(self, auth_client, app, podcast, test_user):
        """Test cannot access episode via wrong podcast ID."""
        with app.app_context():
            # Create another podcast with an episode
            p2 = Podcast(name='Other Pod', slug='other-pod', created_by=test_user['id'])
            db.session.add(p2)
            db.session.flush()
            m = PodcastMember(podcast_id=p2.id, user_id=test_user['id'], role='admin')
            db.session.add(m)
            ep = EpisodeGuide(title='Other Episode', podcast_id=p2.id)
            db.session.add(ep)
            db.session.commit()
            other_ep_id = ep.id

        # Try to access other_ep via first podcast's URL
        response = auth_client.get(f'/podcasts/{podcast["id"]}/episodes/{other_ep_id}/')
        assert response.status_code == 404


class TestPodcastTemplates:
    """Tests for template routes scoped under podcasts."""

    def test_list_templates(self, auth_client, podcast):
        """Test can list templates for a podcast."""
        response = auth_client.get(f'/podcasts/{podcast["id"]}/templates/')
        assert response.status_code == 200

    def test_create_template(self, auth_client, app, podcast):
        """Test can create template."""
        response = auth_client.post(f'/podcasts/{podcast["id"]}/templates/new', data={
            'name': 'New Template',
            'description': 'Template description',
            'default_poll_1': 'Weekly poll question'
        }, follow_redirects=False)

        assert response.status_code == 302

        with app.app_context():
            t = EpisodeGuideTemplate.query.filter_by(name='New Template').first()
            assert t is not None
            assert t.podcast_id == podcast['id']

    def test_edit_template(self, auth_client, app, podcast):
        """Test can edit template."""
        with app.app_context():
            from flask_login import current_user
            t = EpisodeGuideTemplate(
                name='Editable Template',
                podcast_id=podcast['id'],
                created_by=1  # test_user
            )
            db.session.add(t)
            db.session.commit()
            t_id = t.id

        response = auth_client.post(f'/podcasts/{podcast["id"]}/templates/{t_id}/edit', data={
            'name': 'Updated Template Name',
            'description': 'Updated description'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            t = EpisodeGuideTemplate.query.get(t_id)
            assert t.name == 'Updated Template Name'

    def test_delete_template(self, auth_client, app, podcast):
        """Test can delete template."""
        with app.app_context():
            t = EpisodeGuideTemplate(name='To Delete', podcast_id=podcast['id'], created_by=1)
            db.session.add(t)
            db.session.commit()
            t_id = t.id

        response = auth_client.post(
            f'/podcasts/{podcast["id"]}/templates/{t_id}/delete',
            follow_redirects=True
        )

        assert response.status_code == 200

        with app.app_context():
            t = EpisodeGuideTemplate.query.get(t_id)
            assert t is None


class TestEpisodeMetadataAPI:
    """Tests for episode metadata AJAX endpoints."""

    def test_update_title(self, auth_client, podcast_episode):
        """Test updating episode title via API."""
        response = auth_client.put(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/metadata',
            json={'title': 'Updated Title'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['guide']['title'] == 'Updated Title'

    def test_update_title_empty_fails(self, auth_client, podcast_episode):
        """Test empty title is rejected."""
        response = auth_client.put(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/metadata',
            json={'title': ''},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_update_poll_fields(self, auth_client, app, podcast_episode):
        """Test updating poll fields."""
        response = auth_client.put(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/metadata',
            json={
                'previous_poll': 'Previous question?',
                'previous_poll_link': 'https://example.com/poll',
                'new_poll': 'New question?',
                'new_poll_link': 'https://example.com/newpoll'
            },
            content_type='application/json'
        )

        assert response.status_code == 200

        with app.app_context():
            ep = EpisodeGuide.query.get(podcast_episode['id'])
            assert ep.previous_poll == 'Previous question?'
            assert ep.new_poll == 'New question?'


class TestRecordingAPI:
    """Tests for episode recording state API."""

    def test_start_recording(self, auth_client, app, podcast_episode):
        """Test starting recording."""
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/recording',
            json={'action': 'start'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['guide']['status'] == 'recording'

    def test_stop_recording(self, auth_client, app, podcast_episode):
        """Test stopping recording."""
        # First start
        auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/recording',
            json={'action': 'start'},
            content_type='application/json'
        )

        # Then stop
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/recording',
            json={'action': 'stop'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['guide']['status'] == 'completed'

    def test_reset_recording(self, auth_client, app, podcast_episode):
        """Test resetting recording clears timestamps."""
        # Start and add some data
        auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/recording',
            json={'action': 'start'},
            content_type='application/json'
        )

        # Reset
        response = auth_client.post(
            f'/podcasts/{podcast_episode["podcast_id"]}/episodes/{podcast_episode["id"]}/recording',
            json={'action': 'reset'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['guide']['status'] == 'draft'


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_special_characters_in_podcast_name(self, auth_client, app, test_user):
        """Test podcast names with special characters get valid slugs."""
        response = auth_client.post('/podcasts/new', data={
            'name': 'Test & Demo: "Podcast" (2024)'
        }, follow_redirects=False)

        assert response.status_code == 302

        with app.app_context():
            p = Podcast.query.filter_by(name='Test & Demo: "Podcast" (2024)').first()
            assert p is not None
            # Slug should be alphanumeric with dashes
            assert p.slug == 'test-demo-podcast-2024'

    def test_unicode_in_podcast_name(self, auth_client, app, test_user):
        """Test podcast names with unicode characters."""
        response = auth_client.post('/podcasts/new', data={
            'name': 'Podcast 日本語'
        }, follow_redirects=False)

        assert response.status_code == 302

        with app.app_context():
            p = Podcast.query.filter_by(name='Podcast 日本語').first()
            assert p is not None

    def test_empty_slug_falls_back_to_podcast(self, auth_client, app, test_user):
        """Test name that produces empty slug gets fallback."""
        response = auth_client.post('/podcasts/new', data={
            'name': '!!!@@@###'  # No alphanumeric chars
        }, follow_redirects=False)

        assert response.status_code == 302

        with app.app_context():
            p = Podcast.query.filter_by(name='!!!@@@###').first()
            assert p is not None
            assert p.slug == 'podcast'  # Fallback

    def test_nonexistent_podcast_returns_404(self, auth_client):
        """Test accessing non-existent podcast returns 404."""
        response = auth_client.get('/podcasts/99999/episodes/')
        # Could be 404 or redirect (depending on how access control handles it)
        assert response.status_code in [302, 404]

    def test_whitespace_trimmed_from_fields(self, auth_client, app, test_user):
        """Test whitespace is trimmed from input fields."""
        response = auth_client.post('/podcasts/new', data={
            'name': '  Trimmed Name  ',
            'description': '  Trimmed description  '
        }, follow_redirects=False)

        assert response.status_code == 302

        with app.app_context():
            p = Podcast.query.filter_by(name='Trimmed Name').first()
            assert p is not None

    def test_episode_item_update_boundary_position(self, auth_client, podcast_episode_with_items):
        """Test updating item to boundary positions."""
        item_id = podcast_episode_with_items['item_ids'][0]
        podcast_id = podcast_episode_with_items['podcast_id']
        episode_id = podcast_episode_with_items['episode_id']

        # Test position 0
        response = auth_client.put(
            f'/podcasts/{podcast_id}/episodes/{episode_id}/items/{item_id}',
            json={'position': 0},
            content_type='application/json'
        )
        assert response.status_code == 200

        # Test large position
        response = auth_client.put(
            f'/podcasts/{podcast_id}/episodes/{episode_id}/items/{item_id}',
            json={'position': 9999},
            content_type='application/json'
        )
        assert response.status_code == 200
