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

    # --- ESTATE SELECTION ---
    # Every estate page lives under /e/<slug>/, so the estate a page was
    # rendered for is in its URL, every link and every form it posts. Two tabs
    # on two estates stay two estates: a form left open on one cannot write
    # into the other, which a "current estate" cookie could not promise.
    from flask import g, session, abort, request
    from src import estates as estate_registry

    app.config.setdefault('ESTATES_ROOT', app.instance_path)

    @app.url_value_preprocessor
    def pull_estate(endpoint, values):
        if values and 'estate' in values:
            g.estate = values.pop('estate')

    @app.url_defaults
    def add_estate(endpoint, values):
        if 'estate' not in values and g.get('estate') and \
                app.url_map.is_endpoint_expecting(endpoint, 'estate'):
            values['estate'] = g.estate

    @app.before_request
    def check_estate():
        slug = g.get('estate')
        if slug is None:
            return
        entry = estate_registry.get(app.config['ESTATES_ROOT'], slug) \
            if estate_registry.SLUG_RE.match(slug) else None
        if entry is None:
            g.estate = None
            abort(404)
        g.estate_entry = entry
        session['estate'] = slug

    # --- TEMPLATE GLOBALS ---
    @app.context_processor
    def inject_estate():
        """Which estate is on screen. Shown on every page so demo data and real
        data are never one unlabelled tab apart."""
        entry = g.get('estate_entry')
        return {
            'estate': entry,
            'estate_list': estate_registry.load(app.config['ESTATES_ROOT']),
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
    from src.routes.estates import bp as estates_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(estates_bp)
    # Everything that reads or writes estate data is under /e/<slug>/.
    app.register_blueprint(main_bp, url_prefix='/e/<estate>')
    app.register_blueprint(settings_bp, url_prefix='/e/<estate>/settings')
    app.register_blueprint(manage_bp, url_prefix='/e/<estate>/manage')

    return app

# For Gunicorn
app = create_app()