import os
import secrets
from pathlib import Path

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system env vars

BASE_DIR = Path(__file__).parent.absolute()


def get_database_url():
    """Get database URL, handling PostgreSQL URL format variations."""
    url = os.environ.get('DATABASE_URL')
    if url:
        # Fix postgres:// to postgresql:// (Railway/Heroku use postgres://)
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url
    return f'sqlite:///{BASE_DIR}/mouse_domination.db'


def is_sqlite():
    """Check if using SQLite database."""
    return get_database_url().startswith('sqlite://')


def get_secret_key():
    """Get secret key from environment or generate for development."""
    key = os.environ.get('SECRET_KEY')
    if key:
        return key

    # Check if we're in production mode
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError(
            "SECRET_KEY environment variable must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # Development mode: generate a random key (will change on restart)
    return secrets.token_hex(32)


class Config:
    """Base configuration."""
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database connection pooling (for PostgreSQL/MySQL only)
    # SQLite doesn't support these options
    SQLALCHEMY_ENGINE_OPTIONS = {} if is_sqlite() else {
        'pool_size': 10,           # Number of connections to keep open
        'pool_recycle': 3600,      # Recycle connections after 1 hour
        'pool_pre_ping': True,     # Verify connections before use
        'max_overflow': 20,        # Allow up to 20 additional connections
    }

    # Security settings
    DEBUG = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Backup settings
    BACKUP_DIR = BASE_DIR / 'backups'
    BACKUP_RETENTION_DAYS = 30

    # YouTube API settings
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    YOUTUBE_CHANNEL_ID = os.environ.get('YOUTUBE_CHANNEL_ID')  # Your channel ID

    # Creator channel settings (for outreach templates)
    CREATOR_CHANNEL_NAME = os.environ.get('CREATOR_CHANNEL_NAME', 'dazztrazak')
    CREATOR_CHANNEL_STATS = os.environ.get('CREATOR_CHANNEL_STATS', '4,000+ subscribers')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        # Validate required production settings
        if not os.environ.get('SECRET_KEY'):
            raise RuntimeError("SECRET_KEY must be set in production")


class TestConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    SESSION_COOKIE_SECURE = False
    # SQLite doesn't support connection pooling options
    SQLALCHEMY_ENGINE_OPTIONS = {}
