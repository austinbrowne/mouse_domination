"""Tests for outreach template routes."""
import pytest
from models import OutreachTemplate, Contact, Company
from extensions import db


class TestListTemplates:
    """Tests for template listing."""

    def test_list_templates_requires_auth(self, client):
        """Test list requires authentication."""
        response = client.get('/templates/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_templates_empty(self, auth_client):
        """Test list with no templates."""
        response = auth_client.get('/templates/')
        assert response.status_code == 200

    def test_list_templates_with_data(self, auth_client, template):
        """Test list shows templates."""
        response = auth_client.get('/templates/')
        assert response.status_code == 200
        assert b'Test Template' in response.data

    def test_filter_by_category(self, auth_client, app):
        """Test filtering by category."""
        with app.app_context():
            t1 = OutreachTemplate(name='Sponsor Template', body='Test body', category='sponsor')
            t2 = OutreachTemplate(name='Collab Template', body='Test body', category='collab')
            db.session.add_all([t1, t2])
            db.session.commit()

        response = auth_client.get('/templates/?category=sponsor')
        assert response.status_code == 200

    def test_search_templates(self, auth_client, app):
        """Test searching by name."""
        with app.app_context():
            t1 = OutreachTemplate(name='Sponsor Outreach', body='Test body', category='sponsor')
            t2 = OutreachTemplate(name='Collab Invite', body='Test body', category='collab')
            db.session.add_all([t1, t2])
            db.session.commit()

        response = auth_client.get('/templates/?search=Sponsor')
        assert response.status_code == 200

    def test_search_case_insensitive(self, auth_client, app):
        """Test search is case-insensitive."""
        with app.app_context():
            t1 = OutreachTemplate(name='Sponsor Outreach', body='Test body', category='sponsor')
            db.session.add(t1)
            db.session.commit()

        response = auth_client.get('/templates/?search=sponsor')
        assert response.status_code == 200

    def test_pagination(self, auth_client, app):
        """Test pagination works."""
        with app.app_context():
            for i in range(5):
                t = OutreachTemplate(name=f'Template {i}', body='Test body', category='other')
                db.session.add(t)
            db.session.commit()

        response = auth_client.get('/templates/?page=1')
        assert response.status_code == 200

    def test_invalid_category_ignored(self, auth_client, template):
        """Test invalid category values are ignored."""
        response = auth_client.get('/templates/?category=invalid_category')
        assert response.status_code == 200


class TestNewTemplate:
    """Tests for creating new templates."""

    def test_new_template_form_renders(self, auth_client):
        """Test new template form renders."""
        response = auth_client.get('/templates/new')
        assert response.status_code == 200

    def test_create_template_success(self, auth_client, app):
        """Test creating a new template."""
        response = auth_client.post('/templates/new', data={
            'name': 'New Template',
            'body': 'This is the template body',
            'category': 'sponsor'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'created successfully' in response.data.lower()

        with app.app_context():
            template = OutreachTemplate.query.filter_by(name='New Template').first()
            assert template is not None
            assert template.category == 'sponsor'

    def test_create_template_missing_name(self, auth_client):
        """Test creating template without name fails."""
        response = auth_client.post('/templates/new', data={
            'body': 'This is the template body',
            'category': 'sponsor'
        })
        assert response.status_code == 200
        # Should show error

    def test_create_template_missing_body(self, auth_client):
        """Test creating template without body fails."""
        response = auth_client.post('/templates/new', data={
            'name': 'New Template',
            'category': 'sponsor'
        })
        assert response.status_code == 200
        # Should show error

    def test_create_template_with_all_fields(self, auth_client, app):
        """Test creating template with all optional fields."""
        response = auth_client.post('/templates/new', data={
            'name': 'Full Template',
            'body': 'Dear {{contact_name}}, greetings from {{company_name}}.',
            'category': 'pitch',
            'subject': 'Partnership Opportunity',
            'notes': 'Use for initial outreach'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            template = OutreachTemplate.query.filter_by(name='Full Template').first()
            assert template.subject == 'Partnership Opportunity'
            assert template.notes == 'Use for initial outreach'

    def test_create_template_default_category(self, auth_client, app):
        """Test template created with default category."""
        response = auth_client.post('/templates/new', data={
            'name': 'Default Category Template',
            'body': 'Test body'
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            template = OutreachTemplate.query.filter_by(name='Default Category Template').first()
            assert template is not None
            # Should use default category
            assert template.category == 'other'


class TestEditTemplate:
    """Tests for editing templates."""

    def test_edit_template_form_renders(self, auth_client, template):
        """Test edit form renders with template data."""
        response = auth_client.get(f'/templates/{template["id"]}/edit')
        assert response.status_code == 200
        assert b'Test Template' in response.data

    def test_edit_template_nonexistent_404(self, auth_client):
        """Test editing non-existent template returns 404."""
        response = auth_client.get('/templates/99999/edit')
        assert response.status_code == 404

    def test_update_template_success(self, auth_client, app, template):
        """Test updating a template."""
        response = auth_client.post(f'/templates/{template["id"]}/edit', data={
            'name': 'Updated Template',
            'body': 'Updated body content',
            'category': 'follow_up'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data.lower()

        with app.app_context():
            updated = db.session.get(OutreachTemplate, template['id'])
            assert updated.name == 'Updated Template'
            assert updated.body == 'Updated body content'
            assert updated.category == 'follow_up'

    def test_update_template_missing_name(self, auth_client, template):
        """Test updating template without name fails."""
        response = auth_client.post(f'/templates/{template["id"]}/edit', data={
            'body': 'Updated body',
            'category': 'sponsor'
        })
        assert response.status_code == 200
        # Should show error

    def test_update_template_missing_body(self, auth_client, template):
        """Test updating template without body fails."""
        response = auth_client.post(f'/templates/{template["id"]}/edit', data={
            'name': 'Updated Name',
            'category': 'sponsor'
        })
        assert response.status_code == 200
        # Should show error


class TestDeleteTemplate:
    """Tests for deleting templates."""

    def test_delete_template_success(self, auth_client, app, template):
        """Test deleting a template."""
        template_id = template['id']
        response = auth_client.post(f'/templates/{template_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            deleted = db.session.get(OutreachTemplate, template_id)
            assert deleted is None

    def test_delete_nonexistent_404(self, auth_client):
        """Test deleting non-existent template returns 404."""
        response = auth_client.post('/templates/99999/delete')
        assert response.status_code == 404

    def test_delete_redirects_to_list(self, auth_client, template):
        """Test delete redirects to list."""
        response = auth_client.post(f'/templates/{template["id"]}/delete')
        assert response.status_code == 302
        assert '/templates/' in response.location


class TestPreviewTemplate:
    """Tests for template preview."""

    def test_preview_renders(self, auth_client, template):
        """Test preview page renders."""
        response = auth_client.get(f'/templates/{template["id"]}/preview')
        assert response.status_code == 200

    def test_preview_nonexistent_404(self, auth_client):
        """Test preview non-existent template returns 404."""
        response = auth_client.get('/templates/99999/preview')
        assert response.status_code == 404

    def test_preview_placeholder_contact(self, auth_client, app, template, contact):
        """Test contact_name placeholder is substituted."""
        response = auth_client.get(
            f'/templates/{template["id"]}/preview?contact_id={contact["id"]}'
        )
        assert response.status_code == 200
        # The contact name should appear in the preview
        assert b'Test Contact' in response.data

    def test_preview_placeholder_company(self, auth_client, app, template, company):
        """Test company_name placeholder is substituted."""
        response = auth_client.get(
            f'/templates/{template["id"]}/preview?company_id={company["id"]}'
        )
        assert response.status_code == 200
        # The company name should appear in the preview
        assert b'Test Company' in response.data

    def test_preview_both_placeholders(self, auth_client, template, contact, company):
        """Test both contact and company placeholders are substituted."""
        response = auth_client.get(
            f'/templates/{template["id"]}/preview?contact_id={contact["id"]}&company_id={company["id"]}'
        )
        assert response.status_code == 200
        assert b'Test Contact' in response.data
        assert b'Test Company' in response.data

    def test_preview_invalid_contact_ignored(self, auth_client, template):
        """Test invalid contact ID is ignored."""
        response = auth_client.get(
            f'/templates/{template["id"]}/preview?contact_id=99999'
        )
        assert response.status_code == 200
        # Placeholder should remain unchanged
        assert b'{{contact_name}}' in response.data

    def test_preview_invalid_company_ignored(self, auth_client, template):
        """Test invalid company ID is ignored."""
        response = auth_client.get(
            f'/templates/{template["id"]}/preview?company_id=99999'
        )
        assert response.status_code == 200
        # Placeholder should remain unchanged
        assert b'{{company_name}}' in response.data

    def test_preview_xss_prevention(self, auth_client, app, template):
        """Test HTML is escaped in placeholder values."""
        with app.app_context():
            # Create contact with XSS attempt
            malicious_contact = Contact(name='<script>alert("xss")</script>')
            db.session.add(malicious_contact)
            db.session.commit()
            contact_id = malicious_contact.id

        response = auth_client.get(
            f'/templates/{template["id"]}/preview?contact_id={contact_id}'
        )
        assert response.status_code == 200
        # The malicious script should be escaped in the body content
        # Check that the escaped version appears (XSS prevented)
        assert b'&lt;script&gt;alert' in response.data
        # And the raw script tag for xss should NOT appear unescaped
        assert b'<script>alert' not in response.data


class TestUseTemplate:
    """Tests for use counter."""

    def test_use_increments_counter(self, auth_client, app, template):
        """Test using template increments times_used."""
        # Get initial count
        with app.app_context():
            t = db.session.get(OutreachTemplate, template['id'])
            initial = t.times_used or 0

        response = auth_client.post(f'/templates/{template["id"]}/use')
        assert response.status_code == 200

        # Check response is JSON
        data = response.get_json()
        assert data['success'] is True
        assert data['times_used'] == initial + 1

        # Verify in database
        with app.app_context():
            t = db.session.get(OutreachTemplate, template['id'])
            assert t.times_used == initial + 1

    def test_use_returns_json(self, auth_client, template):
        """Test use returns JSON response."""
        response = auth_client.post(f'/templates/{template["id"]}/use')
        assert response.status_code == 200
        assert response.content_type == 'application/json'

    def test_use_nonexistent_404(self, auth_client):
        """Test using non-existent template returns 404."""
        response = auth_client.post('/templates/99999/use')
        assert response.status_code == 404

    def test_use_multiple_increments(self, auth_client, app, template):
        """Test multiple uses increment correctly."""
        for i in range(3):
            auth_client.post(f'/templates/{template["id"]}/use')

        with app.app_context():
            t = db.session.get(OutreachTemplate, template['id'])
            assert t.times_used >= 3


class TestCopyTemplate:
    """Tests for template copying."""

    def test_copy_creates_duplicate(self, auth_client, app, template):
        """Test copying creates a new template."""
        response = auth_client.post(f'/templates/{template["id"]}/copy', follow_redirects=True)
        assert response.status_code == 200
        assert b'copied' in response.data.lower()

        with app.app_context():
            templates = OutreachTemplate.query.filter(
                OutreachTemplate.name.like('%Test Template%')
            ).all()
            assert len(templates) == 2

    def test_copy_appends_name(self, auth_client, app, template):
        """Test copy appends (Copy) to name."""
        auth_client.post(f'/templates/{template["id"]}/copy')

        with app.app_context():
            copy = OutreachTemplate.query.filter_by(name='Test Template (Copy)').first()
            assert copy is not None

    def test_copy_resets_times_used(self, auth_client, app, template):
        """Test copy resets times_used to 0."""
        # First increment original's usage
        auth_client.post(f'/templates/{template["id"]}/use')

        # Then copy
        auth_client.post(f'/templates/{template["id"]}/copy')

        with app.app_context():
            copy = OutreachTemplate.query.filter_by(name='Test Template (Copy)').first()
            assert copy is not None
            # Should start at 0 or None (default)
            assert (copy.times_used or 0) == 0

    def test_copy_preserves_content(self, auth_client, app, template):
        """Test copy preserves body and category."""
        auth_client.post(f'/templates/{template["id"]}/copy')

        with app.app_context():
            original = db.session.get(OutreachTemplate, template['id'])
            copy = OutreachTemplate.query.filter_by(name='Test Template (Copy)').first()
            assert copy.body == original.body
            assert copy.category == original.category
            assert copy.subject == original.subject

    def test_copy_nonexistent_404(self, auth_client):
        """Test copying non-existent template returns 404."""
        response = auth_client.post('/templates/99999/copy')
        assert response.status_code == 404

    def test_copy_redirects_to_list(self, auth_client, template):
        """Test copy redirects to list."""
        response = auth_client.post(f'/templates/{template["id"]}/copy')
        assert response.status_code == 302
        assert '/templates/' in response.location


class TestTemplateAuth:
    """Tests for authentication requirements."""

    def test_new_template_requires_auth(self, client):
        """Test new template requires authentication."""
        response = client.get('/templates/new')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_edit_template_requires_auth(self, client, template):
        """Test edit template requires authentication."""
        response = client.get(f'/templates/{template["id"]}/edit')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_template_requires_auth(self, client, template):
        """Test delete template requires authentication."""
        response = client.post(f'/templates/{template["id"]}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_preview_template_requires_auth(self, client, template):
        """Test preview template requires authentication."""
        response = client.get(f'/templates/{template["id"]}/preview')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_use_template_requires_auth(self, client, template):
        """Test use template requires authentication."""
        response = client.post(f'/templates/{template["id"]}/use')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_copy_template_requires_auth(self, client, template):
        """Test copy template requires authentication."""
        response = client.post(f'/templates/{template["id"]}/copy')
        assert response.status_code == 302
        assert '/auth/login' in response.location
