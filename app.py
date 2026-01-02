from flask import Flask
from config import Config
from src.extensions import db, migrate

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='src/templates', static_folder='src/static')
    app.config.from_object(config_class)
    
    # Run security checks
    config_class.init_app(app)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Import models so Alembic can detect them
    from src import models

    # --- CUSTOM FILTERS ---
    @app.template_filter('currency')
    def currency_filter(value):
        """Format currency: $1,000 or $1,000.50 (no decimals if integer)."""
        try:
            val = float(value)
            if val.is_integer():
                return "${:,.0f}".format(val)
            return "${:,.2f}".format(val)
        except (ValueError, TypeError):
            return value

    # --- BLUEPRINT REGISTRATION ---
    from src.routes.auth import bp as auth_bp
    from src.routes.main import bp as main_bp
    from src.routes.settings import bp as settings_bp
    from src.routes.manage import bp as manage_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(manage_bp)

    return app

# For Gunicorn
app = create_app()