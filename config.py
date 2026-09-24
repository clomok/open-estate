import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///instance/estate.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

    # Which dataset this instance is serving. See datasets/README.md.
    DATASET = os.environ.get('DATASET', 'demo')
    DATASET_LABEL = os.environ.get('DATASET_LABEL', '')
    DATASET_PROTECTED = os.environ.get('DATASET_PROTECTED', '0') == '1'

    @staticmethod
    def init_app(app):
        # Security Check
        if not Config.ADMIN_PASSWORD or Config.ADMIN_PASSWORD == 'change_me_immediately':
            raise ValueError("CRITICAL: ADMIN_PASSWORD is not set in the dataset env file.")

        # Without a real SECRET_KEY, Flask cannot sign the session cookie that
        # the login is built on - fail here rather than at the first login.
        if not Config.SECRET_KEY or Config.SECRET_KEY == 'dev_key_change_this_to_random_string':
            raise ValueError("CRITICAL: SECRET_KEY is not set in the dataset env file.")

        # Ensure instance folder exists
        try:
            os.makedirs(app.instance_path)
        except OSError:
            pass
