from flask import Blueprint

bp = Blueprint('content_dev', __name__)

from app.blueprints.content_dev import routes
