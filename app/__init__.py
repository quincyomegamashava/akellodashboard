from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
from config import Config


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Force template reloading
db = SQLAlchemy(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
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
from app import mobile_meeting_sales_routes  # noqa: F401 — /api/mobile/meeting-notes & sales-marketing
from app import pm_routes  # noqa: F401 — extended PM platform routes
from app import game_race_routes  # noqa: F401 — multiplayer game races

# Register the global deletion-audit listener (after models are loaded).
from app.audit import init_audit
init_audit(app, db)

# Import ASL MTD settings routes
from app import routes_asl_settings

# Import and register database routes
from app.database_routes import database_bp
app.register_blueprint(database_bp)

from app.migration_routes import migration_bp
app.register_blueprint(migration_bp)

from app.schema_studio_routes import schema_studio_bp
app.register_blueprint(schema_studio_bp)

from app.blueprints.content_dev import bp as content_dev_bp
app.register_blueprint(content_dev_bp)

from app.blueprints.new_creations import bp as new_creations_bp
from app.blueprints.new_creations import models as new_creations_models  # noqa: F401
app.register_blueprint(new_creations_bp)

from app.blueprints.meeting_notes import bp as meeting_notes_bp
from app.blueprints.meeting_notes import models as meeting_notes_models  # noqa: F401
app.register_blueprint(meeting_notes_bp)

try:
    from app.blueprints.help_desk import bp as help_desk_bp
    from app.blueprints.help_desk import models as help_desk_models  # noqa: F401
    app.register_blueprint(help_desk_bp)
    logger.info("Help Desk blueprint registered (/help-desk/)")
except Exception:
    logger.exception("Help Desk blueprint failed to register")

try:
    from app.blueprints.student_export import bp as student_export_bp

    app.register_blueprint(student_export_bp)
    logger.info("Student export blueprint registered (/student-export/)")
except Exception:
    logger.exception("Student export blueprint failed to register")

try:
    from app.blueprints.sales_marketing import bp as sales_marketing_bp
    from app.blueprints.sales_marketing import models as sales_marketing_models  # noqa: F401

    app.register_blueprint(sales_marketing_bp)
    logger.info("Sales & Marketing blueprint registered (/sales-marketing/)")
except Exception:
    logger.exception("Sales & Marketing blueprint failed to register")

try:
    from app.blueprints.akello_revenue import bp as akello_revenue_bp
    from app.blueprints.akello_revenue import models as akello_revenue_models  # noqa: F401

    app.register_blueprint(akello_revenue_bp)
    logger.info("Akello Revenue blueprint registered (/akello-revenue/)")
except Exception:
    logger.exception("Akello Revenue blueprint failed to register")

from app.blueprints.learn_admin import bp as learn_admin_bp
from app.blueprints.learn_api import bp as learn_api_bp
from app.blueprints.learn_guardian import bp as learn_guardian_bp
from app.blueprints.learn_portal import bp as learn_portal_bp

app.register_blueprint(learn_portal_bp)
app.register_blueprint(learn_guardian_bp)
app.register_blueprint(learn_admin_bp)
app.register_blueprint(learn_api_bp)
csrf.exempt(learn_api_bp)

from app.learning_hub import models as learning_hub_models  # noqa: F401

try:
    with app.app_context():
        from app.games.seed_stem_games import seed_stem_games
        _stem_seed = seed_stem_games()
        logger.info("HBC/STEM games seeded: %s", _stem_seed)
except Exception:
    logger.exception("STEM game seed skipped (games table may not exist yet)")
    try:
        db.session.rollback()
    except Exception:
        pass

# Start helpdesk email fetch scheduler (every 60s)
from app.scheduler import start_scheduler
start_scheduler(app)
