import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # Each estate is its own SQLite file under ESTATES_ROOT (see src/estates.py);
    # the engine is chosen per request. Flask-SQLAlchemy still insists on a
    # default URI, so it gets an in-memory one that nothing ever reads.
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

    # Where estates.json and estates/<slug>/ live. Unset = the Flask instance
    # folder, which is /app/instance in the container. See datasets/README.md.
    if os.environ.get('ESTATES_ROOT'):
        ESTATES_ROOT = os.environ['ESTATES_ROOT']

    @staticmethod
    def init_app(app):
        # Security Check
        if not Config.ADMIN_PASSWORD or Config.ADMIN_PASSWORD == 'change_me_immediately':
            raise ValueError("CRITICAL: ADMIN_PASSWORD is not set in datasets/site.env.")

        # Without a real SECRET_KEY, Flask cannot sign the session cookie that
        # the login is built on - fail here rather than at the first login.
        if not Config.SECRET_KEY or Config.SECRET_KEY == 'dev_key_change_this_to_random_string':
            raise ValueError("CRITICAL: SECRET_KEY is not set in datasets/site.env.")

        # Ensure instance folder exists
        try:
            os.makedirs(app.instance_path)
        except OSError:
            pass
