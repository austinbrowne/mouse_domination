import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()


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
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR}/mouse_domination.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Backup settings
    BACKUP_DIR = BASE_DIR / 'backups'
    BACKUP_RETENTION_DAYS = 30

    # YouTube API settings
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    YOUTUBE_CHANNEL_ID = os.environ.get('YOUTUBE_CHANNEL_ID')  # Your channel ID


class TestConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
