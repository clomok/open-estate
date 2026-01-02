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
    
    # Configure SQLite for WAL mode (Concurrency)
    from sqlalchemy import event
    with app.app_context():
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            try:
                @event.listens_for(db.engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.close()
            except:
                pass # Already attached

    # Import models so Alembic can detect them
    from src import models

    # --- FIXED IMPORTS AND REGISTRATION ---
    # We import the blueprints specifically from their files
    from src.routes.auth import bp as auth_bp
    from src.routes.main import bp as main_bp
    from src.routes.settings import bp as settings_bp
    from src.routes.manage import bp as manage_bp

    # We register them using the variables we just defined above
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(manage_bp)

    return app

# For Gunicorn
app = create_app()