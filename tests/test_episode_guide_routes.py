"""Tests for Episode Guide routes."""
import pytest
from models import EpisodeGuide, EpisodeGuideItem, EpisodeGuideTemplate
from extensions import db


class TestEpisodeGuideList:
    """Tests for episode guide list routes."""

    def test_list_requires_auth(self, client):
        """Test list requires authentication."""
        response = client.get('/guide/')
        assert response.status_code == 302  # Redirect to login

    def test_list_empty(self, auth_client):
        """Test list with no guides."""
        response = auth_client.get('/guide/')
        assert response.status_code == 200
        assert b'No episode guides yet' in response.data

    def test_list_with_guides(self, auth_client, guide):
        """Test list shows guides."""
        response = auth_client.get('/guide/')
        assert response.status_code == 200
        assert b'Test Episode' in response.data

    def test_filter_by_status(self, auth_client, app):
        """Test filtering by status."""
        with app.app_context():
            guide1 = EpisodeGuide(title='Draft Guide', status='draft')
            guide2 = EpisodeGuide(title='Completed Guide', status='completed')
            db.session.add_all([guide1, guide2])
            db.session.commit()

        response = auth_client.get('/guide/?status=completed')
        assert response.status_code == 200
        assert b'Completed Guide' in response.data
        assert b'Draft Guide' not in response.data

    def test_search_guide_title(self, auth_client, app):
        """Test search finds guide by title."""
        with app.app_context():
            guide = EpisodeGuide(title='Unique Mouse Review')
            db.session.add(guide)
            db.session.commit()

        response = auth_client.get('/guide/?search=Unique%20Mouse')
        assert response.status_code == 200
        assert b'Unique Mouse Review' in response.data

    def test_search_item_title(self, auth_client, app):
        """Test search finds guide by item title."""
        with app.app_context():
            guide = EpisodeGuide(title='Episode 100')
            db.session.add(guide)
            db.session.commit()

            item = EpisodeGuideItem(
                guide_id=guide.id,
                section='introduction',
                title='Razer Viper V3 Pro Review'
            )
            db.session.add(item)
            db.session.commit()

        response = auth_client.get('/guide/?search=Razer%20Viper')
        assert response.status_code == 200
        assert b'Episode 100' in response.data

    def test_search_item_links(self, auth_client, app):
        """Test search finds guide by item link URL."""
        with app.app_context():
            guide = EpisodeGuide(title='Episode With Links')
            db.session.add(guide)
            db.session.commit()

            item = EpisodeGuideItem(
                guide_id=guide.id,
                section='introduction',
                title='Some Topic',
                links=['https://unique-domain.com/article']
            )
            db.session.add(item)
            db.session.commit()

        response = auth_client.get('/guide/?search=unique-domain')
        assert response.status_code == 200
        assert b'Episode With Links' in response.data


class TestEpisodeGuideCreate:
    """Tests for episode guide creation."""

    def test_create_guide(self, auth_client, app):
        """Test creating a new guide."""
        response = auth_client.post('/guide/new', data={
            'title': 'New Test Episode',
            'episode_number': '99'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            guide = EpisodeGuide.query.filter_by(title='New Test Episode').first()
            assert guide is not None
            assert guide.episode_number == 99
            assert guide.status == 'draft'

    def test_create_requires_title(self, auth_client):
        """Test creating guide without title fails."""
        response = auth_client.post('/guide/new', data={
            'episode_number': '99'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'required' in response.data.lower() or b'error' in response.data.lower()

    def test_copy_guide(self, auth_client, app, guide_with_items):
        """Test copying a guide copies its items."""
        response = auth_client.post(
            f'/guide/new-from/{guide_with_items["guide_id"]}',
            follow_redirects=True
        )
        assert response.status_code == 200

        with app.app_context():
            # Should have 2 guides now
            guides = EpisodeGuide.query.all()
            assert len(guides) == 2

            # New guide should have copied items
            new_guide = EpisodeGuide.query.filter(
                EpisodeGuide.title.like('Copy of%')
            ).first()
            assert new_guide is not None
            assert len(new_guide.items) == 2

    def test_copy_preserves_links(self, auth_client, app, guide_with_items):
        """Test copying guide preserves multi-links on items."""
        auth_client.post(
            f'/guide/new-from/{guide_with_items["guide_id"]}',
            follow_redirects=True
        )

        with app.app_context():
            new_guide = EpisodeGuide.query.filter(
                EpisodeGuide.title.like('Copy of%')
            ).first()

            # Find item with multiple links
            multi_link_item = next(
                (i for i in new_guide.items if len(i.all_links) > 1),
                None
            )
            assert multi_link_item is not None
            assert len(multi_link_item.all_links) == 2


class TestEpisodeGuideItems:
    """Tests for episode guide item AJAX endpoints."""

    def test_add_item_title_only(self, auth_client, app, guide):
        """Test adding item with just title."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item'
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['title'] == 'Test Item'

    def test_add_item_with_notes(self, auth_client, app, guide):
        """Test adding item with notes - THIS WOULD CATCH THE REGRESSION."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item',
                'notes': 'Important notes here'
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['notes'] == 'Important notes here'

        # Verify in database
        with app.app_context():
            item = EpisodeGuideItem.query.filter_by(
                guide_id=guide['id'],
                title='Test Item'
            ).first()
            assert item.notes == 'Important notes here'

    def test_add_item_with_single_link(self, auth_client, app, guide):
        """Test adding item with single link."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item',
                'links': ['https://example.com']
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['item']['links'] == ['https://example.com']

    def test_add_item_with_multiple_links(self, auth_client, app, guide):
        """Test adding item with multiple links."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item',
                'links': ['https://example.com', 'https://test.com', 'https://third.com']
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data['item']['links']) == 3
        assert 'https://example.com' in data['item']['links']
        assert 'https://test.com' in data['item']['links']

    def test_add_item_filters_empty_links(self, auth_client, app, guide):
        """Test empty strings are filtered from links."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'introduction',
                'title': 'Test Item',
                'links': ['https://example.com', '', '  ', 'https://test.com']
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['item']['links'] == ['https://example.com', 'https://test.com']

    def test_update_item_title(self, auth_client, app, guide_with_items):
        """Test updating item title."""
        item_id = guide_with_items['item_ids'][0]
        guide_id = guide_with_items['guide_id']

        response = auth_client.put(
            f'/guide/{guide_id}/items/{item_id}',
            json={'title': 'Updated Title'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['item']['title'] == 'Updated Title'

    def test_update_item_links(self, auth_client, app, guide_with_items):
        """Test updating item links."""
        item_id = guide_with_items['item_ids'][0]
        guide_id = guide_with_items['guide_id']

        response = auth_client.put(
            f'/guide/{guide_id}/items/{item_id}',
            json={'links': ['https://new-link.com', 'https://another.com']},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['item']['links'] == ['https://new-link.com', 'https://another.com']

    def test_update_item_notes(self, auth_client, app, guide_with_items):
        """Test updating item notes."""
        item_id = guide_with_items['item_ids'][0]
        guide_id = guide_with_items['guide_id']

        response = auth_client.put(
            f'/guide/{guide_id}/items/{item_id}',
            json={'notes': 'Updated notes'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['item']['notes'] == 'Updated notes'

    def test_delete_item(self, auth_client, app, guide_with_items):
        """Test deleting an item."""
        item_id = guide_with_items['item_ids'][0]
        guide_id = guide_with_items['guide_id']

        response = auth_client.delete(
            f'/guide/{guide_id}/items/{item_id}',
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # Verify deleted
        with app.app_context():
            item = db.session.get(EpisodeGuideItem, item_id)
            assert item is None

    def test_item_requires_title(self, auth_client, guide):
        """Test adding item without title fails."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'introduction',
                'title': ''
            },
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_item_invalid_section(self, auth_client, guide):
        """Test adding item with invalid section fails."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'invalid_section',
                'title': 'Test'
            },
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False


class TestEpisodeGuideLiveMode:
    """Tests for live recording mode."""

    def test_start_recording(self, auth_client, app, guide):
        """Test starting recording."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/start',
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g.status == 'recording'
            assert g.recording_started_at is not None

    def test_stop_recording(self, auth_client, app, guide):
        """Test stopping recording."""
        # Start first
        auth_client.post(f'/guide/{guide["id"]}/start')

        # Stop
        response = auth_client.post(
            f'/guide/{guide["id"]}/stop',
            json={'elapsed_seconds': 3600},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g.status == 'completed'
            assert g.total_duration_seconds == 3600

    def test_capture_timestamp(self, auth_client, app, guide_with_items):
        """Test capturing timestamp for item."""
        item_id = guide_with_items['item_ids'][0]
        guide_id = guide_with_items['guide_id']

        # Start recording first
        auth_client.post(f'/guide/{guide_id}/start')

        response = auth_client.post(
            f'/guide/{guide_id}/timestamp/{item_id}',
            json={'elapsed_seconds': 125},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['timestamp_seconds'] == 125

        with app.app_context():
            item = db.session.get(EpisodeGuideItem, item_id)
            assert item.timestamp_seconds == 125
            assert item.discussed is True

    def test_reopen_guide(self, auth_client, app, guide):
        """Test reopening a completed guide."""
        # Complete the guide first
        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            g.status = 'completed'
            db.session.commit()

        response = auth_client.post(
            f'/guide/{guide["id"]}/reopen',
            follow_redirects=True
        )

        assert response.status_code == 200

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g.status == 'draft'


class TestEpisodeGuideDelete:
    """Tests for episode guide deletion."""

    def test_delete_guide(self, auth_client, app, guide):
        """Test deleting a guide."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/delete',
            follow_redirects=True
        )

        assert response.status_code == 200

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g is None

    def test_delete_cascades_items(self, auth_client, app, guide_with_items):
        """Test deleting guide removes items."""
        guide_id = guide_with_items['guide_id']
        item_ids = guide_with_items['item_ids']

        auth_client.post(f'/guide/{guide_id}/delete', follow_redirects=True)

        with app.app_context():
            for item_id in item_ids:
                item = db.session.get(EpisodeGuideItem, item_id)
                assert item is None

    def test_delete_nonexistent_404(self, auth_client):
        """Test deleting non-existent guide returns 404."""
        response = auth_client.post('/guide/99999/delete')
        assert response.status_code == 404


class TestEpisodeGuideTemplates:
    """Tests for episode guide template management."""

    def test_list_templates_requires_auth(self, client):
        """Test list templates requires authentication."""
        response = client.get('/guide/templates')
        assert response.status_code == 302  # Redirect to login

    def test_list_templates_empty(self, auth_client):
        """Test list with no templates."""
        response = auth_client.get('/guide/templates')
        assert response.status_code == 200
        assert b'No templates yet' in response.data

    def test_new_template_form(self, auth_client):
        """Test new template form renders."""
        response = auth_client.get('/guide/templates/new')
        assert response.status_code == 200
        assert b'New Episode Guide Template' in response.data

    def test_create_template_success(self, auth_client, app):
        """Test creating a template."""
        response = auth_client.post('/guide/templates/new', data={
            'name': 'Test Template',
            'description': 'A test template',
            'default_sections': ['introduction', 'outro'],
            'intro_static_content': 'Welcome\nSubscribe',
            'outro_static_content': 'Thanks for listening',
            'default_poll_1': 'What mouse do you use?',
        }, follow_redirects=True)

        assert response.status_code == 200

        from models import EpisodeGuideTemplate
        with app.app_context():
            template = EpisodeGuideTemplate.query.filter_by(name='Test Template').first()
            assert template is not None
            assert template.description == 'A test template'
            assert template.intro_static_content == ['Welcome', 'Subscribe']
            assert template.outro_static_content == ['Thanks for listening']
            assert template.default_poll_1 == 'What mouse do you use?'

    def test_edit_template_success(self, auth_client, app):
        """Test editing a template."""
        from models import EpisodeGuideTemplate
        with app.app_context():
            template = EpisodeGuideTemplate(name='Original Name')
            db.session.add(template)
            db.session.commit()
            template_id = template.id

        response = auth_client.post(f'/guide/templates/{template_id}/edit', data={
            'name': 'Updated Name',
            'description': 'Updated description',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            template = db.session.get(EpisodeGuideTemplate, template_id)
            assert template.name == 'Updated Name'
            assert template.description == 'Updated description'

    def test_delete_template_success(self, auth_client, app):
        """Test deleting a template without guides."""
        from models import EpisodeGuideTemplate
        with app.app_context():
            template = EpisodeGuideTemplate(name='To Delete')
            db.session.add(template)
            db.session.commit()
            template_id = template.id

        response = auth_client.post(f'/guide/templates/{template_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            template = db.session.get(EpisodeGuideTemplate, template_id)
            assert template is None

    def test_delete_template_with_guides_blocked(self, auth_client, app):
        """Test cannot delete template used by guides."""
        from models import EpisodeGuideTemplate
        with app.app_context():
            template = EpisodeGuideTemplate(name='In Use')
            db.session.add(template)
            db.session.commit()

            guide = EpisodeGuide(title='Uses Template', template_id=template.id)
            db.session.add(guide)
            db.session.commit()
            template_id = template.id

        response = auth_client.post(f'/guide/templates/{template_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'Cannot delete template' in response.data

        with app.app_context():
            template = db.session.get(EpisodeGuideTemplate, template_id)
            assert template is not None

    def test_new_guide_shows_template_selector(self, auth_client, app):
        """Test that new guide form shows template selector."""
        # Create a template first
        with app.app_context():
            template = EpisodeGuideTemplate(name='My Template', is_default=True)
            db.session.add(template)
            db.session.commit()

        response = auth_client.get('/guide/new')
        assert response.status_code == 200
        assert b'Start from Template' in response.data
        assert b'My Template' in response.data
        assert b'(Default)' in response.data

    def test_new_guide_shows_create_template_link_when_none(self, auth_client):
        """Test that new guide form shows link to create template when none exist."""
        response = auth_client.get('/guide/new')
        assert response.status_code == 200
        assert b'Start from Template' in response.data
        assert b'No templates yet' in response.data
        assert b'Create one' in response.data

    def test_create_guide_with_template_applies_defaults(self, auth_client, app):
        """Test that creating guide with template applies intro/outro/sections."""
        # Create a template with content
        with app.app_context():
            template = EpisodeGuideTemplate(
                name='Full Template',
                intro_static_content=['Welcome!', 'Subscribe'],
                outro_static_content=['Thanks for watching'],
                default_sections=[{'key': 'custom_1', 'name': 'Special Segment'}],
                default_poll_1='Best mouse?',
                is_default=False
            )
            db.session.add(template)
            db.session.commit()
            template_id = template.id

        response = auth_client.post('/guide/new', data={
            'title': 'Guide With Template',
            'template_id': template_id,
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            guide = EpisodeGuide.query.filter_by(title='Guide With Template').first()
            assert guide is not None
            assert guide.template_id == template_id
            assert guide.intro_static_content == ['Welcome!', 'Subscribe']
            assert guide.outro_static_content == ['Thanks for watching']
            assert guide.custom_sections == [{'key': 'custom_1', 'name': 'Special Segment'}]
            assert guide.new_poll == 'Best mouse?'

    def test_create_guide_without_template_has_no_defaults(self, auth_client, app):
        """Test that creating guide without template has no pre-filled content."""
        response = auth_client.post('/guide/new', data={
            'title': 'Blank Guide',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            guide = EpisodeGuide.query.filter_by(title='Blank Guide').first()
            assert guide is not None
            assert guide.template_id is None
            assert guide.intro_static_content is None
            assert guide.outro_static_content is None
            assert guide.custom_sections is None


class TestCustomSections:
    """Tests for on-the-fly custom sections."""

    def test_add_custom_section(self, auth_client, app, guide):
        """Test adding a custom section to a guide."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/sections',
            json={'name': 'Q&A Session'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['section']['name'] == 'Q&A Session'
        assert data['section']['key'] == 'qa_session'

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g.custom_sections is not None
            assert len(g.custom_sections) == 1
            assert g.custom_sections[0]['name'] == 'Q&A Session'

    def test_add_custom_section_empty_name(self, auth_client, guide):
        """Test adding custom section with empty name fails."""
        response = auth_client.post(
            f'/guide/{guide["id"]}/sections',
            json={'name': ''},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_add_item_to_custom_section(self, auth_client, app, guide):
        """Test adding items to a custom section."""
        # First add the custom section
        auth_client.post(
            f'/guide/{guide["id"]}/sections',
            json={'name': 'Hot Takes'},
            content_type='application/json'
        )

        # Then add an item to it
        response = auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={
                'section': 'hot_takes',
                'title': 'Mice are overrated'
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['item']['section'] == 'hot_takes'

    def test_delete_custom_section_empty(self, auth_client, app, guide):
        """Test deleting an empty custom section."""
        # Add then delete
        auth_client.post(
            f'/guide/{guide["id"]}/sections',
            json={'name': 'To Delete'},
            content_type='application/json'
        )

        response = auth_client.delete(
            f'/guide/{guide["id"]}/sections/to_delete'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g.custom_sections is None or len(g.custom_sections) == 0

    def test_delete_builtin_section_blocked(self, auth_client, guide):
        """Test cannot delete built-in sections."""
        response = auth_client.delete(
            f'/guide/{guide["id"]}/sections/introduction'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'built-in' in data['error'].lower()

    def test_delete_section_with_items_blocked(self, auth_client, app, guide):
        """Test cannot delete custom section with items."""
        # Add custom section
        auth_client.post(
            f'/guide/{guide["id"]}/sections',
            json={'name': 'With Items'},
            content_type='application/json'
        )

        # Add an item
        auth_client.post(
            f'/guide/{guide["id"]}/items',
            json={'section': 'with_items', 'title': 'Test Item'},
            content_type='application/json'
        )

        # Try to delete
        response = auth_client.delete(
            f'/guide/{guide["id"]}/sections/with_items'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'items' in data['error'].lower()


class TestStaticContent:
    """Tests for dynamic static content."""

    def test_update_static_content(self, auth_client, app, guide):
        """Test updating intro/outro static content."""
        response = auth_client.put(
            f'/guide/{guide["id"]}/static-content',
            json={
                'intro_static_content': ['Hello', 'Welcome'],
                'outro_static_content': ['Goodbye', 'Subscribe']
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['intro_static_content'] == ['Hello', 'Welcome']
        assert data['outro_static_content'] == ['Goodbye', 'Subscribe']

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g.intro_static_content == ['Hello', 'Welcome']
            assert g.outro_static_content == ['Goodbye', 'Subscribe']

    def test_update_static_content_string_format(self, auth_client, app, guide):
        """Test updating static content with newline-separated string."""
        response = auth_client.put(
            f'/guide/{guide["id"]}/static-content',
            json={
                'intro_static_content': "Line 1\nLine 2\nLine 3"
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['intro_static_content'] == ['Line 1', 'Line 2', 'Line 3']

    def test_clear_static_content(self, auth_client, app, guide):
        """Test clearing static content."""
        # First set some content
        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            g.intro_static_content = ['Hello']
            db.session.commit()

        # Then clear it
        response = auth_client.put(
            f'/guide/{guide["id"]}/static-content',
            json={'intro_static_content': []},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['intro_static_content'] == []

        with app.app_context():
            g = db.session.get(EpisodeGuide, guide['id'])
            assert g.intro_static_content is None
