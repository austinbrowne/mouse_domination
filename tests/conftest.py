import pytest
import re
from app import create_app, db
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
def client(app):
    """Create test client."""
    return app.test_client()


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
