"""Logging configuration for the application."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(app):
    """Configure application logging."""
    # Create logs directory if it doesn't exist
    log_dir = Path(app.root_path) / 'logs'
    log_dir.mkdir(exist_ok=True)

    # Set up file handler with rotation
    file_handler = RotatingFileHandler(
        log_dir / 'app.log',
        maxBytes=1024 * 1024,  # 1MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    ))
    file_handler.setLevel(logging.INFO)

    # Set up console handler for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(levelname)s [%(name)s] %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG if app.debug else logging.WARNING)

    # Configure app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)

    # Configure SQLAlchemy logger for query debugging (only in debug mode)
    if app.debug:
        sql_logger = logging.getLogger('sqlalchemy.engine')
        sql_logger.setLevel(logging.WARNING)  # Set to INFO to see queries

    app.logger.info('Logging initialized')


def get_logger(name):
    """Get a logger instance for a module."""
    return logging.getLogger(name)
