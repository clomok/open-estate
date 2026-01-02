from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# We define these here so other files can import them without creating loops
db = SQLAlchemy()
migrate = Migrate()