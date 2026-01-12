import pytest
import re
from flask_login import login_user
from app import create_app, db
from models import User, EpisodeGuide, EpisodeGuideItem
from config import TestConfig


class CSRFEnabledTestConfig(TestConfig):
    """Test configuration with CSRF enabled."""
    WTF_CSRF_ENABLED = True
    WTF_CSRF_CHECK_DEFAULT = True


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def test_user(app):
    """Create an approved test user."""
    with app.app_context():
        user = User(
            email='test@example.com',
            name='Test User',
            is_approved=True,
            is_admin=False
        )
        user.set_password('TestPassword123!')
        db.session.add(user)
        db.session.commit()
        # Store the ID before leaving context
        user_id = user.id
    # Return a dict with user info that persists
    return {'id': user_id, 'email': 'test@example.com', 'password': 'TestPassword123!'}


@pytest.fixture
def admin_user(app):
    """Create an approved admin user."""
    with app.app_context():
        user = User(
            email='admin@example.com',
            name='Admin User',
            is_approved=True,
            is_admin=True
        )
        user.set_password('AdminPassword123!')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {'id': user_id, 'email': 'admin@example.com', 'password': 'AdminPassword123!'}


@pytest.fixture
def client(app):
    """Create test client (unauthenticated)."""
    return app.test_client()


@pytest.fixture
def auth_client(app, test_user):
    """Create authenticated test client by logging in."""
    client = app.test_client()
    # Login via the login endpoint
    client.post('/auth/login', data={
        'email': test_user['email'],
        'password': test_user['password']
    })
    return client


@pytest.fixture
def admin_client(app, admin_user):
    """Create authenticated admin test client by logging in."""
    client = app.test_client()
    # Login via the login endpoint
    client.post('/auth/login', data={
        'email': admin_user['email'],
        'password': admin_user['password']
    })
    return client


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def csrf_app():
    """Create application with CSRF protection enabled for testing."""
    app = create_app(CSRFEnabledTestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def csrf_client(csrf_app):
    """Create test client with CSRF protection enabled."""
    return csrf_app.test_client()


@pytest.fixture
def csrf_test_user(csrf_app):
    """Create an approved test user for CSRF app."""
    with csrf_app.app_context():
        user = User(
            email='test@example.com',
            name='Test User',
            is_approved=True,
            is_admin=False
        )
        user.set_password('TestPassword123!')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {'id': user_id, 'email': 'test@example.com', 'password': 'TestPassword123!'}


@pytest.fixture
def csrf_auth_client(csrf_app, csrf_test_user):
    """Create authenticated test client with CSRF protection enabled."""
    from tests.conftest import get_csrf_token

    client = csrf_app.test_client()
    # Get CSRF token for login
    token = get_csrf_token(client, '/auth/login')
    # Login via the login endpoint
    client.post('/auth/login', data={
        'csrf_token': token,
        'email': csrf_test_user['email'],
        'password': csrf_test_user['password']
    })
    return client


def get_csrf_token(client, url='/'):
    """Helper to extract CSRF token from a page.

    Args:
        client: Test client instance
        url: URL to fetch to get a CSRF token

    Returns:
        str: CSRF token value
    """
    response = client.get(url)
    # Look for csrf_token in meta tag or hidden field
    html = response.data.decode('utf-8')

    # Try meta tag first
    meta_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    if meta_match:
        return meta_match.group(1)

    # Try hidden input field
    input_match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
    if input_match:
        return input_match.group(1)

    return None


@pytest.fixture
def guide(app):
    """Create a test episode guide."""
    with app.app_context():
        guide = EpisodeGuide(title='Test Episode', status='draft')
        db.session.add(guide)
        db.session.commit()
        guide_id = guide.id
    return {'id': guide_id, 'title': 'Test Episode'}


@pytest.fixture
def guide_with_items(app, guide):
    """Create guide with sample items including multi-links."""
    with app.app_context():
        item1 = EpisodeGuideItem(
            guide_id=guide['id'],
            section='introduction',
            title='Item 1',
            links=['https://example.com'],
            notes='Notes 1',
            position=0
        )
        item2 = EpisodeGuideItem(
            guide_id=guide['id'],
            section='news_mice',
            title='Item 2',
            links=['https://test1.com', 'https://test2.com'],
            position=0
        )
        db.session.add_all([item1, item2])
        db.session.commit()
        item1_id, item2_id = item1.id, item2.id
    return {'guide_id': guide['id'], 'item_ids': [item1_id, item2_id]}
