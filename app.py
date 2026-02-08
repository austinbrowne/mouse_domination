import os
from flask import Flask, g
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config, DevelopmentConfig, ProductionConfig
from extensions import db, csrf, login_manager, limiter, migrate
import uuid


def get_config():
    """Get configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig
    return DevelopmentConfig


def create_app(config_class=None):
    """Application factory pattern."""
    if config_class is None:
        config_class = get_config()

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Trust proxy headers (Cloudflare, nginx, etc.)
    # x_for=1: trust X-Forwarded-For for client IP
    # x_proto=1: trust X-Forwarded-Proto for HTTPS detection
    if os.environ.get('FLASK_ENV') == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Initialize Google OAuth
    from services.google_oauth import init_google_oauth
    init_google_oauth(app)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = 'basic'  # 'strong' can cause issues in Docker/proxy setups

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    # Add request ID for logging context
    @app.before_request
    def add_request_id():
        g.request_id = str(uuid.uuid4())[:8]

    # Backward compatibility: set g.current_user from Flask-Login
    @app.before_request
    def set_current_user():
        g.current_user = current_user if current_user.is_authenticated else None

    # Inject common variables into all templates
    @app.context_processor
    def inject_common():
        from datetime import date
        return {
            'now': date.today(),
            'APP_NAME': app.config.get('APP_NAME', 'Creator Hub'),
            'APP_TAGLINE': app.config.get('APP_TAGLINE', 'Built for Creators'),
            'ENABLE_EPISODE_GUIDE': app.config.get('ENABLE_EPISODE_GUIDE', True),
        }

    # Add security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if not app.debug:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.tailwindcss.com cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' cdn.tailwindcss.com fonts.googleapis.com; "
                "font-src 'self' data: fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://accounts.google.com; "
                "form-action 'self' https://accounts.google.com"
            )
        return response

    # Setup logging
    from utils.logging import setup_logging
    setup_logging(app)

    # Register blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.contacts import contacts_bp
    from routes.companies import companies_bp
    from routes.inventory import inventory_bp
    from routes.affiliates import affiliates_bp
    from routes.collabs import collabs_bp
    from routes.pipeline import pipeline_bp
    from routes.templates import templates_bp
    from routes.podcasts import podcast_bp
    from routes.media_kit import media_kit_bp
    from routes.calendar import calendar_bp
    from routes.settings import settings_bp
    from routes.revenue import revenue_bp
    from routes.content_atomizer import atomizer_bp
    from routes.social import social_bp
    from routes.google_auth import google_auth_bp
    from routes.public_api import public_api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(google_auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(contacts_bp, url_prefix='/contacts')
    app.register_blueprint(companies_bp, url_prefix='/companies')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(affiliates_bp, url_prefix='/affiliates')
    app.register_blueprint(collabs_bp, url_prefix='/collabs')
    app.register_blueprint(pipeline_bp, url_prefix='/pipeline')
    app.register_blueprint(templates_bp, url_prefix='/templates')
    app.register_blueprint(podcast_bp, url_prefix='/podcasts')
    app.register_blueprint(media_kit_bp, url_prefix='/media-kit')
    app.register_blueprint(calendar_bp, url_prefix='/calendar')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(revenue_bp, url_prefix='/revenue')
    app.register_blueprint(atomizer_bp, url_prefix='/atomizer')
    app.register_blueprint(social_bp, url_prefix='/social')
    app.register_blueprint(public_api_bp, url_prefix='/api/v1/public')
    csrf.exempt(public_api_bp)

    if not app.config.get('PUBLIC_API_KEY'):
        app.logger.warning('PUBLIC_API_KEY is not set — public API will return 503')

    return app


if __name__ == '__main__':
    app = create_app()
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port)
