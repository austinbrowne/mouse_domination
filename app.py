from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
csrf = CSRFProtect()


def create_app(config_class=Config):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from routes.main import main_bp
    from routes.contacts import contacts_bp
    from routes.companies import companies_bp
    from routes.inventory import inventory_bp
    from routes.videos import videos_bp
    from routes.podcast import podcast_bp
    from routes.affiliates import affiliates_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(contacts_bp, url_prefix='/contacts')
    app.register_blueprint(companies_bp, url_prefix='/companies')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(videos_bp, url_prefix='/videos')
    app.register_blueprint(podcast_bp, url_prefix='/podcast')
    app.register_blueprint(affiliates_bp, url_prefix='/affiliates')

    # Create database tables
    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    # Use 0.0.0.0 to allow access from other devices on the network
    app.run(debug=True, host='0.0.0.0', port=5000)
