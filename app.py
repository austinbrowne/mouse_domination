import os
from flask import Flask, g
from flask_login import current_user
from config import Config, DevelopmentConfig, ProductionConfig
from extensions import db, csrf, login_manager, limiter
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

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = 'strong'

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
                "script-src 'self' 'unsafe-inline' cdn.tailwindcss.com cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' cdn.tailwindcss.com fonts.googleapis.com; "
                "font-src 'self' fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self'"
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
    from routes.episode_guide import episode_guide_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(contacts_bp, url_prefix='/contacts')
    app.register_blueprint(companies_bp, url_prefix='/companies')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(affiliates_bp, url_prefix='/affiliates')
    app.register_blueprint(collabs_bp, url_prefix='/collabs')
    app.register_blueprint(pipeline_bp, url_prefix='/pipeline')
    app.register_blueprint(templates_bp, url_prefix='/templates')
    app.register_blueprint(episode_guide_bp, url_prefix='/guide')

    # Create database tables
    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port)
