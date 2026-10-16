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

    # --- TEMPLATE GLOBALS ---
    @app.context_processor
    def inject_dataset():
        """Which estate is on screen. Shown on every page so demo data and real
        data are never one unlabelled tab apart."""
        return {
            'dataset_label': app.config.get('DATASET_LABEL', ''),
            'dataset_protected': app.config.get('DATASET_PROTECTED', False),
        }

    # --- CUSTOM FILTERS ---
    # Money is stored as int cents; these are the only places it becomes text.
    from src.money import format_cents, cents_to_input
    from src.holding_types import display_value, mask

    @app.template_filter('currency')
    def currency_filter(cents):
        """Cents -> "$1,000" or "$1,000.50" (no decimals when they are zero)."""
        try:
            return format_cents(cents)
        except (ValueError, TypeError):
            return cents

    app.jinja_env.filters['money_input'] = cents_to_input

    from datetime import timedelta

    @app.template_filter('relday')
    def relday_filter(d, today):
        """A date as a person says it on the Now page: Today, Tomorrow,
        in 5 days, 3 days overdue, then the date itself further out."""
        if d is None:
            return ''
        n = (d - today).days
        if n == 0:
            return 'Today'
        if n == 1:
            return 'Tomorrow'
        if n == -1:
            return 'Yesterday'
        if 1 < n <= 14:
            return f'in {n} days'
        if -14 <= n < -1:
            return f'{-n} days ago'
        return d.strftime('%b %d, %Y') if d.year != today.year else d.strftime('%b %d')

    app.jinja_env.globals['timedelta'] = timedelta
    # Small POST forms (verify, remove) that are not FlaskForms still carry a token.
    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['csrf_token'] = generate_csrf
    app.jinja_env.filters['mask'] = mask
    app.jinja_env.globals['display_value'] = display_value

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