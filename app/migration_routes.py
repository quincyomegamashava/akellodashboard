"""Admin API routes for database migration status, diagnostics, repair, and upgrades."""

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.database_routes import admin_required
from app.migration_service import (
    get_diagnostics,
    get_health_recommendations,
    get_history,
    get_preflight,
    get_status,
    run_align_schema,
    run_downgrade,
    run_fix_migrations,
    run_merge_heads,
    run_repair,
    run_sync_revision,
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


@migration_bp.route('/api/admin/migrations/preflight', methods=['GET'])
@login_required
@admin_required
def migration_preflight():
    return jsonify(get_preflight())


@migration_bp.route('/api/admin/migrations/health', methods=['GET'])
@login_required
@admin_required
def migration_health():
    return jsonify(get_health_recommendations())


@migration_bp.route('/api/admin/migrations/align-schema', methods=['POST'])
@login_required
@admin_required
def migration_align_schema():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({
            'success': False,
            'error': 'Confirmation required. Send {"confirm": true}.',
        }), 400

    stamp_revision = (data.get('stamp_revision') or '').strip() or None
    before = get_status()
    result = run_align_schema(stamp_revision=stamp_revision)

    if result.get('success'):
        current_app.logger.info(
            'Migration schema align by %s: %s -> stamp %s -> %s',
            current_user.username,
            result.get('stamped_from'),
            result.get('stamped_to'),
            result.get('current_revision'),
        )
    else:
        current_app.logger.error(
            'Migration schema align failed for %s (from %s): %s',
            current_user.username,
            before.get('current_revision'),
            result.get('error'),
        )

    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@migration_bp.route('/api/admin/migrations/sync', methods=['POST'])
@login_required
@admin_required
def migration_sync():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({
            'success': False,
            'error': 'Confirmation required. Send {"confirm": true}.',
        }), 400

    revision = (data.get('revision') or '').strip() or None
    before = get_status()
    result = run_sync_revision(revision=revision)

    if result.get('success'):
        current_app.logger.info(
            'Migration sync by %s: %s -> %s',
            current_user.username,
            result.get('stamped_from'),
            result.get('stamped_to'),
        )
    else:
        current_app.logger.error(
            'Migration sync failed for %s (from %s): %s',
            current_user.username,
            before.get('current_revision'),
            result.get('error'),
        )

    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@migration_bp.route('/api/admin/migrations/downgrade', methods=['POST'])
@login_required
@admin_required
def migration_downgrade():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return jsonify({
            'success': False,
            'error': 'Confirmation required. Send {"confirm": true}.',
        }), 400

    mode = (data.get('mode') or 'one').strip().lower()
    if mode not in ('one', 'to'):
        return jsonify({
            'success': False,
            'error': 'Invalid mode. Use "one" or "to".',
        }), 400

    revision = (data.get('revision') or '').strip() or None
    before = get_status()
    result = run_downgrade(revision=revision, mode=mode)

    if result.get('success'):
        current_app.logger.info(
            'Migration downgrade by %s: %s -> %s (mode=%s)',
            current_user.username,
            result.get('applied_from'),
            result.get('applied_to'),
            mode,
        )
    else:
        current_app.logger.error(
            'Migration downgrade failed for %s (from %s): %s',
            current_user.username,
            before.get('current_revision'),
            result.get('error'),
        )

    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


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
    mode = (data.get('mode') or 'all').strip().lower()
    if mode not in ('all', 'next'):
        return jsonify({
            'success': False,
            'error': 'Invalid mode. Use "all" or "next".',
        }), 400

    revision = (data.get('revision') or '').strip() or None
    if mode == 'next':
        revision = None
    result = run_upgrade(revision=revision, mode=mode)

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
