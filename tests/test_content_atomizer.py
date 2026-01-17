"""Tests for Creator Hub Phase 2: Content Atomizer."""
import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from models import ContentAtomicTemplate, ContentAtomicSnippet, EpisodeGuide
from extensions import db
from services.content_atomizer import (
    ContentAtomizerService,
    ContentAtomizerError,
    AIProviderError,
    ConfigurationError,
)


# ============== Fixtures ==============

@pytest.fixture
def ai_template(app, test_user):
    """Create a test AI prompt template."""
    with app.app_context():
        template = ContentAtomicTemplate(
            user_id=test_user['id'],
            name='Twitter Thread',
            platform='twitter',
            description='Thread-style tweets',
            prompt_template='Transform this into a Twitter thread: {content}',
            max_length=280,
            include_hashtags=True,
            is_default=True,
            is_active=True,
        )
        db.session.add(template)
        db.session.commit()
        return {'id': template.id, 'user_id': test_user['id'], 'platform': 'twitter'}


@pytest.fixture
def other_user_template(app, admin_user):
    """Create a template owned by admin user."""
    with app.app_context():
        template = ContentAtomicTemplate(
            user_id=admin_user['id'],
            name='Admin Template',
            platform='instagram',
            prompt_template='Test prompt {content}',
            max_length=2200,
        )
        db.session.add(template)
        db.session.commit()
        return {'id': template.id, 'user_id': admin_user['id']}


@pytest.fixture
def snippet(app, test_user):
    """Create a test snippet."""
    with app.app_context():
        s = ContentAtomicSnippet(
            user_id=test_user['id'],
            source_type='manual',
            platform='twitter',
            source_content='This is a long podcast episode about technology trends in 2024.',
            generated_content='Tech trends 2024: AI is transforming everything! #tech #AI',
            character_count=55,
            word_count=8,
            status='draft',
            ai_model='gpt-4o-mini',
        )
        db.session.add(s)
        db.session.commit()
        return {'id': s.id, 'user_id': test_user['id'], 'platform': 'twitter'}


@pytest.fixture
def other_user_snippet(app, admin_user):
    """Create a snippet owned by admin user."""
    with app.app_context():
        s = ContentAtomicSnippet(
            user_id=admin_user['id'],
            source_type='manual',
            platform='instagram',
            source_content='Test content',
            generated_content='Test output',
            character_count=11,
            status='draft',
        )
        db.session.add(s)
        db.session.commit()
        return {'id': s.id, 'user_id': admin_user['id']}


@pytest.fixture
def multiple_snippets(app, test_user):
    """Create multiple snippets for list testing."""
    with app.app_context():
        snippets = [
            ContentAtomicSnippet(
                user_id=test_user['id'],
                source_type='manual',
                platform='twitter',
                source_content='Content 1',
                generated_content='Tweet 1',
                character_count=7,
                status='draft',
            ),
            ContentAtomicSnippet(
                user_id=test_user['id'],
                source_type='episode',
                platform='instagram',
                source_content='Content 2',
                generated_content='Instagram post',
                character_count=14,
                status='approved',
            ),
            ContentAtomicSnippet(
                user_id=test_user['id'],
                source_type='manual',
                platform='linkedin',
                source_content='Content 3',
                generated_content='LinkedIn update',
                character_count=15,
                status='published',
            ),
        ]
        for s in snippets:
            db.session.add(s)
        db.session.commit()
        return {'count': 3}


# ============== ContentAtomicTemplate Model Tests ==============

class TestContentAtomicTemplateModel:
    """Tests for ContentAtomicTemplate model."""

    def test_create_template(self, app, test_user):
        """Test creating a basic template."""
        with app.app_context():
            template = ContentAtomicTemplate(
                user_id=test_user['id'],
                name='Test Template',
                platform='twitter',
                prompt_template='Convert to tweet: {content}',
            )
            db.session.add(template)
            db.session.commit()

            assert template.id is not None
            assert template.platform == 'twitter'
            assert template.is_active is True

    def test_platform_constants(self):
        """Test platform constants."""
        assert ContentAtomicTemplate.PLATFORM_TWITTER == 'twitter'
        assert ContentAtomicTemplate.PLATFORM_INSTAGRAM == 'instagram'
        assert ContentAtomicTemplate.PLATFORM_YOUTUBE == 'youtube'
        assert ContentAtomicTemplate.PLATFORM_LINKEDIN == 'linkedin'

    def test_platforms_list(self):
        """Test PLATFORMS list contains all platforms with limits."""
        platforms = ContentAtomicTemplate.PLATFORMS
        assert len(platforms) >= 7
        # Check structure: (key, display_name, max_length)
        twitter = [p for p in platforms if p[0] == 'twitter'][0]
        assert twitter[1] == 'Twitter/X'
        assert twitter[2] == 280

    def test_get_platform_limit(self):
        """Test get_platform_limit method."""
        assert ContentAtomicTemplate.get_platform_limit('twitter') == 280
        assert ContentAtomicTemplate.get_platform_limit('instagram') == 2200
        assert ContentAtomicTemplate.get_platform_limit('unknown') is None

    def test_get_platform_display(self):
        """Test get_platform_display method."""
        assert ContentAtomicTemplate.get_platform_display('twitter') == 'Twitter/X'
        assert ContentAtomicTemplate.get_platform_display('linkedin') == 'LinkedIn'
        assert ContentAtomicTemplate.get_platform_display('unknown') == 'Unknown'

    def test_to_dict(self, app, test_user):
        """Test to_dict serialization."""
        with app.app_context():
            template = ContentAtomicTemplate(
                user_id=test_user['id'],
                name='Test',
                platform='twitter',
                prompt_template='Test {content}',
                tone='casual',
                max_length=280,
                include_hashtags=True,
            )
            db.session.add(template)
            db.session.commit()

            d = template.to_dict()
            assert d['name'] == 'Test'
            assert d['platform'] == 'twitter'
            assert d['platform_display'] == 'Twitter/X'
            assert d['include_hashtags'] is True


# ============== ContentAtomicSnippet Model Tests ==============

class TestContentAtomicSnippetModel:
    """Tests for ContentAtomicSnippet model."""

    def test_create_snippet(self, app, test_user):
        """Test creating a basic snippet."""
        with app.app_context():
            snippet = ContentAtomicSnippet(
                user_id=test_user['id'],
                source_type='manual',
                platform='twitter',
                source_content='Long content',
                generated_content='Short tweet',
                character_count=11,
            )
            db.session.add(snippet)
            db.session.commit()

            assert snippet.id is not None
            assert snippet.status == 'draft'

    def test_source_type_constants(self):
        """Test source type constants."""
        assert ContentAtomicSnippet.SOURCE_MANUAL == 'manual'
        assert ContentAtomicSnippet.SOURCE_EPISODE == 'episode'
        assert ContentAtomicSnippet.SOURCE_TRANSCRIPT == 'transcript'

    def test_status_constants(self):
        """Test status constants."""
        assert ContentAtomicSnippet.STATUS_DRAFT == 'draft'
        assert ContentAtomicSnippet.STATUS_APPROVED == 'approved'
        assert ContentAtomicSnippet.STATUS_PUBLISHED == 'published'

    def test_final_content_property(self, app, test_user):
        """Test final_content returns edited or generated."""
        with app.app_context():
            snippet = ContentAtomicSnippet(
                user_id=test_user['id'],
                platform='twitter',
                source_content='Source',
                generated_content='Generated',
                edited_content=None,
            )
            db.session.add(snippet)
            db.session.commit()

            # Without edit, returns generated
            assert snippet.final_content == 'Generated'

            # With edit, returns edited
            snippet.edited_content = 'Edited version'
            assert snippet.final_content == 'Edited version'

    def test_is_over_limit_property(self, app, test_user):
        """Test is_over_limit property."""
        with app.app_context():
            snippet = ContentAtomicSnippet(
                user_id=test_user['id'],
                platform='twitter',
                source_content='Source',
                generated_content='x' * 300,  # Over 280 limit
            )
            db.session.add(snippet)
            db.session.commit()

            assert snippet.is_over_limit is True

            snippet.generated_content = 'Short'
            assert snippet.is_over_limit is False

    def test_platform_display_property(self, app, test_user):
        """Test platform_display property."""
        with app.app_context():
            snippet = ContentAtomicSnippet(
                user_id=test_user['id'],
                platform='linkedin',
                source_content='Source',
                generated_content='Output',
            )
            assert snippet.platform_display == 'LinkedIn'

    def test_to_dict(self, app, test_user):
        """Test to_dict serialization."""
        with app.app_context():
            snippet = ContentAtomicSnippet(
                user_id=test_user['id'],
                platform='twitter',
                source_content='Source text',
                generated_content='Tweet text',
                character_count=10,
                status='approved',
                ai_model='gpt-4',
            )
            db.session.add(snippet)
            db.session.commit()

            d = snippet.to_dict()
            assert d['platform'] == 'twitter'
            assert d['platform_display'] == 'Twitter/X'
            assert d['status'] == 'approved'
            assert d['ai_model'] == 'gpt-4'


# ============== ContentAtomizerService Tests ==============

class TestContentAtomizerService:
    """Tests for ContentAtomizerService."""

    def test_get_available_platforms(self):
        """Test get_available_platforms returns list."""
        platforms = ContentAtomizerService.get_available_platforms()
        assert 'twitter' in platforms
        assert 'instagram' in platforms
        assert 'linkedin' in platforms

    def test_get_platform_config(self):
        """Test get_platform_config returns config dict."""
        config = ContentAtomizerService.get_platform_config('twitter')
        assert config is not None
        assert config['max_length'] == 280
        assert 'display_name' in config

    def test_is_configured_without_key(self):
        """Test is_configured returns False without API key."""
        service = ContentAtomizerService(api_key=None)
        # Clear any env var
        with patch.dict('os.environ', {}, clear=True):
            service = ContentAtomizerService()
            assert service.is_configured is False

    def test_is_configured_with_key(self):
        """Test is_configured returns True with API key."""
        service = ContentAtomizerService(api_key='test-key')
        assert service.is_configured is True

    def test_build_prompt_default(self):
        """Test _build_prompt creates valid prompt."""
        service = ContentAtomizerService(api_key='test')
        prompt = service._build_prompt('Test content', 'twitter')
        assert 'Test content' in prompt
        assert 'Twitter' in prompt or 'twitter' in prompt.lower()

    def test_build_prompt_with_template(self, app, test_user, ai_template):
        """Test _build_prompt uses template prompt."""
        with app.app_context():
            template = db.session.get(ContentAtomicTemplate, ai_template['id'])
            service = ContentAtomizerService(api_key='test')
            prompt = service._build_prompt('My content', 'twitter', template=template)
            assert 'My content' in prompt

    def test_generate_missing_api_key(self):
        """Test generate raises error without API key."""
        service = ContentAtomizerService(api_key=None)
        with pytest.raises(ConfigurationError):
            service.generate('content', 'twitter')

    def test_generate_invalid_platform(self):
        """Test generate raises error for invalid platform."""
        service = ContentAtomizerService(api_key='test')
        with pytest.raises(ContentAtomizerError) as exc_info:
            service.generate('content', 'invalid_platform')
        assert 'platform' in str(exc_info.value).lower()

    def test_generate_empty_content(self):
        """Test generate raises error for empty content."""
        service = ContentAtomizerService(api_key='test')
        with pytest.raises(ContentAtomizerError) as exc_info:
            service.generate('', 'twitter')
        assert 'content' in str(exc_info.value).lower()

    @patch('services.content_atomizer.requests.post')
    def test_generate_openai_success(self, mock_post):
        """Test successful OpenAI API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Generated tweet #test'}}],
            'model': 'gpt-4o-mini',
            'usage': {'total_tokens': 100},
        }
        mock_post.return_value = mock_response

        service = ContentAtomizerService(provider='openai', api_key='test-key')
        result = service.generate('Long content here', 'twitter')

        assert result['content'] == 'Generated tweet #test'
        assert result['platform'] == 'twitter'
        assert result['character_count'] == 21

    @patch('services.content_atomizer.requests.post')
    def test_generate_openai_rate_limit(self, mock_post):
        """Test OpenAI rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        service = ContentAtomizerService(provider='openai', api_key='test-key')
        with pytest.raises(AIProviderError) as exc_info:
            service.generate('content', 'twitter')
        assert 'rate limit' in str(exc_info.value).lower()

    @patch('services.content_atomizer.requests.post')
    def test_generate_anthropic_success(self, mock_post):
        """Test successful Anthropic API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{'text': 'Generated Instagram caption'}],
            'model': 'claude-3-haiku',
        }
        mock_post.return_value = mock_response

        service = ContentAtomizerService(provider='anthropic', api_key='test-key')
        result = service.generate('Long content', 'instagram')

        assert result['content'] == 'Generated Instagram caption'
        assert result['platform'] == 'instagram'

    @patch('services.content_atomizer.requests.post')
    def test_generate_and_save(self, mock_post, app, test_user):
        """Test generate_and_save creates database record."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Saved tweet'}}],
            'model': 'gpt-4o-mini',
        }
        mock_post.return_value = mock_response

        with app.app_context():
            service = ContentAtomizerService(provider='openai', api_key='test-key')
            snippet = service.generate_and_save(
                user_id=test_user['id'],
                source_content='Long podcast content',
                platform='twitter',
                source_type='manual',
                source_title='Test Episode',
            )

            assert snippet.id is not None
            assert snippet.user_id == test_user['id']
            assert snippet.generated_content == 'Saved tweet'
            assert snippet.status == 'draft'


# ============== Snippet List Route Tests ==============

class TestSnippetListRoute:
    """Tests for snippet list route."""

    def test_list_requires_auth(self, client):
        """Test list requires authentication."""
        response = client.get('/atomizer/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_empty(self, auth_client):
        """Test list with no snippets."""
        response = auth_client.get('/atomizer/')
        assert response.status_code == 200
        assert b'atomizer' in response.data.lower() or b'content' in response.data.lower()

    def test_list_with_data(self, auth_client, snippet):
        """Test list shows snippets."""
        response = auth_client.get('/atomizer/')
        assert response.status_code == 200

    def test_list_filter_by_platform(self, auth_client, multiple_snippets):
        """Test filtering by platform."""
        response = auth_client.get('/atomizer/?platform=twitter')
        assert response.status_code == 200

    def test_list_filter_by_status(self, auth_client, multiple_snippets):
        """Test filtering by status."""
        response = auth_client.get('/atomizer/?status=draft')
        assert response.status_code == 200

    def test_list_pagination(self, auth_client, multiple_snippets):
        """Test pagination works."""
        response = auth_client.get('/atomizer/?page=1')
        assert response.status_code == 200


# ============== Snippet Generate Route Tests ==============

class TestSnippetGenerateRoute:
    """Tests for snippet generation route."""

    def test_generate_form_requires_auth(self, client):
        """Test generate form requires authentication."""
        response = client.get('/atomizer/generate')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_generate_form_renders(self, auth_client):
        """Test generate form renders."""
        response = auth_client.get('/atomizer/generate')
        assert response.status_code == 200
        assert b'platform' in response.data.lower()


# ============== Snippet Edit Route Tests ==============

class TestSnippetEditRoute:
    """Tests for snippet edit route."""

    def test_edit_requires_auth(self, client, snippet):
        """Test edit requires authentication."""
        response = client.get(f'/atomizer/{snippet["id"]}/edit')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_edit_form_renders(self, auth_client, snippet):
        """Test edit form renders."""
        response = auth_client.get(f'/atomizer/{snippet["id"]}/edit')
        assert response.status_code == 200

    def test_edit_nonexistent_404(self, auth_client):
        """Test editing non-existent snippet returns 404."""
        response = auth_client.get('/atomizer/99999/edit')
        assert response.status_code == 404

    def test_edit_other_user_403(self, auth_client, other_user_snippet):
        """Test editing another user's snippet returns 403."""
        response = auth_client.get(f'/atomizer/{other_user_snippet["id"]}/edit')
        assert response.status_code == 403

    def test_edit_success(self, auth_client, app, snippet):
        """Test editing a snippet."""
        response = auth_client.post(f'/atomizer/{snippet["id"]}/edit', data={
            'edited_content': 'Edited tweet content',
            'status': 'approved',
        }, follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            s = db.session.get(ContentAtomicSnippet, snippet['id'])
            assert s.edited_content == 'Edited tweet content'
            assert s.status == 'approved'


# ============== Snippet Delete Route Tests ==============

class TestSnippetDeleteRoute:
    """Tests for snippet delete route."""

    def test_delete_requires_auth(self, client, snippet):
        """Test delete requires authentication."""
        response = client.post(f'/atomizer/{snippet["id"]}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_success(self, auth_client, app, snippet):
        """Test deleting a snippet."""
        snippet_id = snippet['id']
        response = auth_client.post(f'/atomizer/{snippet_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            deleted = db.session.get(ContentAtomicSnippet, snippet_id)
            assert deleted is None

    def test_delete_nonexistent_404(self, auth_client):
        """Test deleting non-existent snippet returns 404."""
        response = auth_client.post('/atomizer/99999/delete')
        assert response.status_code == 404

    def test_delete_other_user_403(self, auth_client, other_user_snippet):
        """Test deleting another user's snippet returns 403."""
        response = auth_client.post(f'/atomizer/{other_user_snippet["id"]}/delete')
        assert response.status_code == 403


# ============== Snippet Approve Route Tests ==============

class TestSnippetApproveRoute:
    """Tests for snippet approve route."""

    def test_approve_success(self, auth_client, app, snippet):
        """Test approving a snippet."""
        response = auth_client.post(f'/atomizer/{snippet["id"]}/approve', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            s = db.session.get(ContentAtomicSnippet, snippet['id'])
            assert s.status == 'approved'

    def test_approve_other_user_403(self, auth_client, other_user_snippet):
        """Test approving another user's snippet returns 403."""
        response = auth_client.post(f'/atomizer/{other_user_snippet["id"]}/approve')
        assert response.status_code == 403


# ============== Template List Route Tests ==============

class TestTemplateListRoute:
    """Tests for template list route."""

    def test_list_requires_auth(self, client):
        """Test list requires authentication."""
        response = client.get('/atomizer/templates')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_list_empty(self, auth_client):
        """Test list with no templates."""
        response = auth_client.get('/atomizer/templates')
        assert response.status_code == 200

    def test_list_with_data(self, auth_client, ai_template):
        """Test list shows templates."""
        response = auth_client.get('/atomizer/templates')
        assert response.status_code == 200
        assert b'Twitter Thread' in response.data


# ============== Template Create Route Tests ==============

class TestTemplateCreateRoute:
    """Tests for template creation route."""

    def test_create_form_requires_auth(self, client):
        """Test create form requires authentication."""
        response = client.get('/atomizer/templates/new')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_create_form_renders(self, auth_client):
        """Test create form renders."""
        response = auth_client.get('/atomizer/templates/new')
        assert response.status_code == 200
        assert b'template' in response.data.lower()

    def test_create_template_success(self, auth_client, app):
        """Test creating a new template."""
        response = auth_client.post('/atomizer/templates/new', data={
            'name': 'New Template',
            'platform': 'instagram',
            'prompt_template': 'Convert to Instagram: {content}',
            'max_length': '2200',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'created successfully' in response.data.lower()

        with app.app_context():
            template = ContentAtomicTemplate.query.filter_by(name='New Template').first()
            assert template is not None
            assert template.platform == 'instagram'

    def test_create_template_missing_name(self, auth_client):
        """Test creating template without name fails."""
        response = auth_client.post('/atomizer/templates/new', data={
            'platform': 'twitter',
            'prompt_template': 'Test {content}',
        })
        assert response.status_code == 200
        # Should show error


# ============== Template Edit Route Tests ==============

class TestTemplateEditRoute:
    """Tests for template edit route."""

    def test_edit_requires_auth(self, client, ai_template):
        """Test edit requires authentication."""
        response = client.get(f'/atomizer/templates/{ai_template["id"]}/edit')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_edit_form_renders(self, auth_client, ai_template):
        """Test edit form renders."""
        response = auth_client.get(f'/atomizer/templates/{ai_template["id"]}/edit')
        assert response.status_code == 200

    def test_edit_nonexistent_404(self, auth_client):
        """Test editing non-existent template returns 404."""
        response = auth_client.get('/atomizer/templates/99999/edit')
        assert response.status_code == 404

    def test_edit_other_user_403(self, auth_client, other_user_template):
        """Test editing another user's template returns 403."""
        response = auth_client.get(f'/atomizer/templates/{other_user_template["id"]}/edit')
        assert response.status_code == 403

    def test_edit_success(self, auth_client, app, ai_template):
        """Test editing a template."""
        response = auth_client.post(f'/atomizer/templates/{ai_template["id"]}/edit', data={
            'name': 'Updated Template',
            'platform': 'twitter',
            'prompt_template': 'Updated prompt {content}',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data.lower()

        with app.app_context():
            t = db.session.get(ContentAtomicTemplate, ai_template['id'])
            assert t.name == 'Updated Template'


# ============== Template Delete Route Tests ==============

class TestTemplateDeleteRoute:
    """Tests for template delete route."""

    def test_delete_requires_auth(self, client, ai_template):
        """Test delete requires authentication."""
        response = client.post(f'/atomizer/templates/{ai_template["id"]}/delete')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_delete_success(self, auth_client, app, ai_template):
        """Test deleting a template."""
        template_id = ai_template['id']
        response = auth_client.post(f'/atomizer/templates/{template_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            deleted = db.session.get(ContentAtomicTemplate, template_id)
            assert deleted is None

    def test_delete_other_user_403(self, auth_client, other_user_template):
        """Test deleting another user's template returns 403."""
        response = auth_client.post(f'/atomizer/templates/{other_user_template["id"]}/delete')
        assert response.status_code == 403


# ============== API Route Tests ==============

class TestAPIRoutes:
    """Tests for API routes."""

    def test_api_platforms(self, auth_client):
        """Test API platforms endpoint."""
        response = auth_client.get('/atomizer/api/platforms')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'platforms' in data
        assert len(data['platforms']) > 0

    def test_api_copy_snippet(self, auth_client, snippet):
        """Test API copy snippet endpoint."""
        response = auth_client.post(f'/atomizer/{snippet["id"]}/copy')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'content' in data

    def test_api_copy_other_user_403(self, auth_client, other_user_snippet):
        """Test API copy returns 403 for other user's snippet."""
        response = auth_client.post(f'/atomizer/{other_user_snippet["id"]}/copy')
        assert response.status_code == 403
