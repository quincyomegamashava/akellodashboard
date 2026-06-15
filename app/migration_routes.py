"""Admin API routes for database migration status and upgrades."""

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.database_routes import admin_required
from app.migration_service import get_history, get_status, run_upgrade

migration_bp = Blueprint('migrations', __name__)


@migration_bp.route('/api/admin/migrations/status', methods=['GET'])
@login_required
@admin_required
def migration_status():
    return jsonify(get_status())


@migration_bp.route('/api/admin/migrations/history', methods=['GET'])
@login_required
@admin_required
def migration_history():
    limit = request.args.get('limit', 20, type=int)
    limit = max(1, min(limit, 100))
    return jsonify(get_history(limit=limit))


@migration_bp.route('/api/admin/migrations/upgrade', methods=['POST'])
@login_required
@admin_required
def migration_upgrade():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({
            'success': False,
            'error': 'Confirmation required. Send {"confirm": true}.',
        }), 400

    before = get_status()
    result = run_upgrade(revision='head')

    if result.get('success'):
        current_app.logger.info(
            'Migration upgrade by %s: %s -> %s',
            current_user.username,
            result.get('applied_from'),
            result.get('applied_to'),
        )
    else:
        current_app.logger.error(
            'Migration upgrade failed for %s (from %s): %s',
            current_user.username,
            before.get('current_revision'),
            result.get('error'),
        )

    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code
