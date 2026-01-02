import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///instance/estate.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

    @staticmethod
    def init_app(app):
        # Security Check
        if not Config.ADMIN_PASSWORD or Config.ADMIN_PASSWORD == 'change_me_immediately':
            raise ValueError("CRITICAL: ADMIN_PASSWORD is not set in .env file.")
        
        # Ensure instance folder exists
        try:
            os.makedirs(app.instance_path)
        except OSError:
            pass