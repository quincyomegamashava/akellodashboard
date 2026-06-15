"""Admin API routes for database migration status, diagnostics, repair, and upgrades."""

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.database_routes import admin_required
from app.migration_service import (
    get_diagnostics,
    get_history,
    get_status,
    run_fix_migrations,
    run_merge_heads,
    run_repair,
    run_upgrade,
)

migration_bp = Blueprint('migrations', __name__)


@migration_bp.route('/api/admin/migrations/status', methods=['GET'])
@login_required
@admin_required
def migration_status():
    return jsonify(get_status())


@migration_bp.route('/api/admin/migrations/diagnostics', methods=['GET'])
@login_required
@admin_required
def migration_diagnostics():
    return jsonify(get_diagnostics())


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


@migration_bp.route('/api/admin/migrations/repair', methods=['POST'])
@login_required
@admin_required
def migration_repair():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({
            'success': False,
            'error': 'Confirmation required. Send {"confirm": true}.',
        }), 400

    stamp_revision = (data.get('stamp_revision') or '').strip()
    if not stamp_revision:
        return jsonify({
            'success': False,
            'error': 'stamp_revision is required.',
        }), 400

    before = get_diagnostics()
    result = run_repair(
        stamp_revision=stamp_revision,
        remove_orphan_files=bool(data.get('remove_orphan_files', True)),
        run_upgrade_after=bool(data.get('run_upgrade_after', True)),
        auto_merge_heads=bool(data.get('auto_merge_heads', False)),
    )

    if result.get('success'):
        current_app.logger.info(
            'Migration repair by %s: %s -> %s (backup=%s)',
            current_user.username,
            result.get('stamped_from'),
            result.get('stamped_to'),
            result.get('backup_path'),
        )
    else:
        current_app.logger.error(
            'Migration repair failed for %s (from %s): %s',
            current_user.username,
            before.get('current_revision'),
            result.get('error'),
        )

    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@migration_bp.route('/api/admin/migrations/merge', methods=['POST'])
@login_required
@admin_required
def migration_merge():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({
            'success': False,
            'error': 'Confirmation required. Send {"confirm": true}.',
        }), 400

    message = (data.get('message') or '').strip() or None
    before = get_diagnostics()
    result = run_merge_heads(message=message)

    if result.get('success'):
        current_app.logger.info(
            'Migration merge by %s: heads %s -> %s',
            current_user.username,
            before.get('head_revisions'),
            result.get('new_revision'),
        )
    else:
        current_app.logger.error(
            'Migration merge failed for %s: %s',
            current_user.username,
            result.get('error'),
        )

    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@migration_bp.route('/api/admin/migrations/fix', methods=['POST'])
@login_required
@admin_required
def migration_fix():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({
            'success': False,
            'error': 'Confirmation required. Send {"confirm": true}.',
        }), 400

    stamp_revision = (data.get('stamp_revision') or '').strip() or None
    before = get_diagnostics()
    result = run_fix_migrations(
        stamp_revision=stamp_revision,
        remove_orphan_files=bool(data.get('remove_orphan_files', True)),
        merge_heads=bool(data.get('merge_heads', True)),
        run_upgrade_after=bool(data.get('run_upgrade_after', True)),
    )

    if result.get('success'):
        current_app.logger.info(
            'Migration fix by %s: %s -> %s (backup=%s)',
            current_user.username,
            result.get('stamped_from'),
            result.get('stamped_to'),
            result.get('backup_path'),
        )
    else:
        current_app.logger.error(
            'Migration fix failed for %s: %s',
            current_user.username,
            result.get('error'),
        )

    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code
