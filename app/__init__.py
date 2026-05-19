from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Force template reloading
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize activity tracking
from app.activity_tracker import ActivityTracker
activity_tracker = ActivityTracker(app)

# Initialize SocketIO handlers
from app.socketio_handlers import init_socketio_handlers
init_socketio_handlers(socketio)

# Setup logging before importing routes
from app.logging_config import setup_logging
logger = setup_logging(app)

from app import routes, models, monitoring_routes

# Register the global deletion-audit listener (after models are loaded).
from app.audit import init_audit
init_audit(app, db)

# Import ASL MTD settings routes
from app import routes_asl_settings

# Import and register database routes
from app.database_routes import database_bp
app.register_blueprint(database_bp)

from app.blueprints.content_dev import bp as content_dev_bp
app.register_blueprint(content_dev_bp)

from app.blueprints.new_creations import bp as new_creations_bp
from app.blueprints.new_creations import models as new_creations_models  # noqa: F401
app.register_blueprint(new_creations_bp)

from app.blueprints.meeting_notes import bp as meeting_notes_bp
from app.blueprints.meeting_notes import models as meeting_notes_models  # noqa: F401
app.register_blueprint(meeting_notes_bp)

# Start helpdesk email fetch scheduler (every 60s)
from app.scheduler import start_scheduler
start_scheduler(app)
