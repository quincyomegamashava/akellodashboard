"""Database Schema Studio — Super-admin phpMyAdmin-style console."""

from __future__ import annotations

import io
import sys

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.auth_decorators import is_super_admin, super_admin_required
from app.ddl_service import (
    execute_ddl_operation,
    execute_sql_query,
    get_schema_activity,
    preview_ddl,
)
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
from app.schema_studio_service import (
    export_table_csv,
    get_column_types_for_dialect,
    get_engine,
    get_overview,
    get_relations,
    get_table_detail,
    get_table_rows,
    list_databases,
    list_tables,
)

schema_studio_bp = Blueprint('schema_studio', __name__)


def _json_error(message: str, status: int = 400):
    return jsonify({'success': False, 'error': message}), status


@schema_studio_bp.route('/admin/schema-studio')
@login_required
def schema_studio_page():
    if not is_super_admin():
        flash('Super-admin access is required for Database Schema Studio.', 'danger')
        return redirect(url_for('overview'))
    return render_template('admin/schema_studio.html', title='Database Studio')


@schema_studio_bp.route('/api/admin/schema-studio/databases')
@login_required
@super_admin_required
def api_list_databases():
    try:
        return jsonify({'success': True, 'databases': list_databases()})
    except Exception as exc:
        current_app.logger.exception('schema-studio list databases')
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/overview')
@login_required
@super_admin_required
def api_overview(db_key):
    exact = request.args.get('exact_counts', 'false').lower() in ('1', 'true', 'yes')
    try:
        return jsonify({'success': True, 'overview': get_overview(db_key, exact_counts=exact)})
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables')
@login_required
@super_admin_required
def api_tables(db_key):
    search = request.args.get('search', '')
    include_counts = request.args.get('include_counts', 'false').lower() in ('1', 'true', 'yes')
    try:
        return jsonify({
            'success': True,
            'tables': list_tables(db_key, search=search, include_counts=include_counts),
        })
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>')
@login_required
@super_admin_required
def api_table_detail(db_key, table_name):
    try:
        detail = get_table_detail(db_key, table_name)
        dialect = get_engine(db_key).dialect.name
        detail['column_types'] = get_column_types_for_dialect(dialect)
        return jsonify({'success': True, 'table': detail})
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>/rows')
@login_required
@super_admin_required
def api_table_rows(db_key, table_name):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    order_by = request.args.get('order_by')
    column_filter = request.args.get('filter')
    try:
        data = get_table_rows(
            db_key,
            table_name,
            page=page,
            per_page=per_page,
            order_by=order_by,
            column_filter=column_filter,
        )
        return jsonify({'success': True, **data})
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>/export')
@login_required
@super_admin_required
def api_export_table(db_key, table_name):
    limit = request.args.get('limit', 10000, type=int)
    try:
        csv_data = export_table_csv(db_key, table_name, limit=limit)
        from flask import Response
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={table_name}.csv',
            },
        )
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/relations')
@login_required
@super_admin_required
def api_relations(db_key):
    prefix = request.args.get('prefix', '')
    try:
        return jsonify({'success': True, **get_relations(db_key, table_prefix=prefix)})
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/column-types')
@login_required
@super_admin_required
def api_column_types(db_key):
    try:
        dialect = get_engine(db_key).dialect.name
        return jsonify({
            'success': True,
            'dialect': dialect,
            'types': get_column_types_for_dialect(dialect),
        })
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/ddl/preview', methods=['POST'])
@login_required
@super_admin_required
def api_ddl_preview(db_key):
    data = request.get_json(silent=True) or {}
    operation = (data.get('operation') or '').strip()
    if not operation:
        return _json_error('operation is required')
    try:
        return jsonify(preview_ddl(operation, db_key, data))
    except Exception as exc:
        return _json_error(str(exc), 500)


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables', methods=['POST'])
@login_required
@super_admin_required
def api_create_table(db_key):
    data = request.get_json(silent=True) or {}
    result = execute_ddl_operation('create_table', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>', methods=['PATCH'])
@login_required
@super_admin_required
def api_rename_table(db_key, table_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    result = execute_ddl_operation('rename_table', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>', methods=['DELETE'])
@login_required
@super_admin_required
def api_drop_table(db_key, table_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    result = execute_ddl_operation('drop_table', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>/columns', methods=['POST'])
@login_required
@super_admin_required
def api_add_column(db_key, table_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    result = execute_ddl_operation('add_column', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route(
    '/api/admin/schema-studio/<db_key>/tables/<table_name>/columns/<column_name>',
    methods=['PATCH'],
)
@login_required
@super_admin_required
def api_alter_column(db_key, table_name, column_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    data['column'] = column_name
    result = execute_ddl_operation('alter_column', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route(
    '/api/admin/schema-studio/<db_key>/tables/<table_name>/columns/<column_name>',
    methods=['DELETE'],
)
@login_required
@super_admin_required
def api_drop_column(db_key, table_name, column_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    data['column'] = column_name
    result = execute_ddl_operation('drop_column', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>/indexes', methods=['POST'])
@login_required
@super_admin_required
def api_create_index(db_key, table_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    result = execute_ddl_operation('create_index', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route(
    '/api/admin/schema-studio/<db_key>/tables/<table_name>/indexes/<index_name>',
    methods=['DELETE'],
)
@login_required
@super_admin_required
def api_drop_index(db_key, table_name, index_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    data['index_name'] = index_name
    result = execute_ddl_operation('drop_index', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/tables/<table_name>/foreign-keys', methods=['POST'])
@login_required
@super_admin_required
def api_add_foreign_key(db_key, table_name):
    data = request.get_json(silent=True) or {}
    data['table'] = table_name
    result = execute_ddl_operation('add_foreign_key', db_key, data)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/<db_key>/query', methods=['POST'])
@login_required
@super_admin_required
def api_query(db_key):
    data = request.get_json(silent=True) or {}
    query = data.get('query', '')
    allow_write = bool(data.get('allow_write', False))
    limit = data.get('limit', 1000)
    result = execute_sql_query(db_key, query, allow_write=allow_write, limit=limit)
    status = 200 if result.get('success') else 400
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/activity')
@login_required
@super_admin_required
def api_activity():
    limit = request.args.get('limit', 50, type=int)
    activity = get_schema_activity(limit=limit)
    return jsonify({
        'success': True,
        'activity': activity,
        'audit_log_url': url_for('admin_audit_log'),
    })


# --- App DB migrations (proxied for studio UI) ---

@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/status')
@login_required
@super_admin_required
def studio_migration_status():
    return jsonify(get_status())


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/diagnostics')
@login_required
@super_admin_required
def studio_migration_diagnostics():
    return jsonify(get_diagnostics())


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/history')
@login_required
@super_admin_required
def studio_migration_history():
    limit = request.args.get('limit', 20, type=int)
    limit = max(1, min(limit, 100))
    return jsonify(get_history(limit=limit))


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/preflight')
@login_required
@super_admin_required
def studio_migration_preflight():
    return jsonify(get_preflight())


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/health')
@login_required
@super_admin_required
def studio_migration_health():
    return jsonify(get_health_recommendations())


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/upgrade', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_upgrade():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')
    mode = (data.get('mode') or 'all').strip().lower()
    revision = (data.get('revision') or '').strip() or None
    if mode == 'next':
        revision = None
    result = run_upgrade(revision=revision, mode=mode)
    status = 200 if result.get('success') else 500
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/downgrade', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_downgrade():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')
    mode = (data.get('mode') or 'one').strip().lower()
    revision = (data.get('revision') or '').strip() or None
    result = run_downgrade(revision=revision, mode=mode)
    status = 200 if result.get('success') else 500
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/repair', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_repair():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')
    stamp_revision = (data.get('stamp_revision') or '').strip()
    if not stamp_revision:
        return _json_error('stamp_revision is required.')
    result = run_repair(
        stamp_revision=stamp_revision,
        remove_orphan_files=bool(data.get('remove_orphan_files', True)),
        run_upgrade_after=bool(data.get('run_upgrade_after', True)),
        auto_merge_heads=bool(data.get('auto_merge_heads', False)),
    )
    status = 200 if result.get('success') else 500
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/merge', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_merge():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')
    message = (data.get('message') or '').strip() or None
    result = run_merge_heads(message=message)
    status = 200 if result.get('success') else 500
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/fix', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_fix():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')
    stamp_revision = (data.get('stamp_revision') or '').strip() or None
    result = run_fix_migrations(
        stamp_revision=stamp_revision,
        remove_orphan_files=bool(data.get('remove_orphan_files', True)),
        merge_heads=bool(data.get('merge_heads', True)),
        run_upgrade_after=bool(data.get('run_upgrade_after', True)),
    )
    status = 200 if result.get('success') else 500
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/align-schema', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_align_schema():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')
    stamp_revision = (data.get('stamp_revision') or '').strip() or None
    result = run_align_schema(stamp_revision=stamp_revision)
    status = 200 if result.get('success') else 500
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/sync', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_sync():
    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')
    revision = (data.get('revision') or '').strip() or None
    result = run_sync_revision(revision=revision)
    status = 200 if result.get('success') else 500
    return jsonify(result), status


@schema_studio_bp.route('/api/admin/schema-studio/app/migrations/generate', methods=['POST'])
@login_required
@super_admin_required
def studio_migration_generate():
    """Autogenerate an Alembic revision from model/schema diff (does not apply)."""
    if not current_app.config.get('ALLOW_WEB_MIGRATIONS', True):
        return _json_error('Web migrations are disabled (ALLOW_WEB_MIGRATIONS=false).')

    data = request.get_json(silent=True) or {}
    if not data.get('confirm'):
        return _json_error('Confirmation required. Send {"confirm": true}.')

    message = (data.get('message') or 'Schema studio autogenerate').strip()
    if not message:
        return _json_error('message is required.')

    try:
        from alembic import command
        from alembic.script import ScriptDirectory

        migrate_ext = current_app.extensions['migrate']
        config = migrate_ext.get_config()

        before_files = set()
        versions_dir = config.get_main_option('version_locations')
        if not versions_dir:
            script = ScriptDirectory.from_config(config)
            versions_dir = script.versions
        import os
        if os.path.isdir(str(versions_dir)):
            before_files = set(os.listdir(str(versions_dir)))

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            command.revision(config, autogenerate=True, message=message)
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        new_files = []
        if os.path.isdir(str(versions_dir)):
            after_files = set(os.listdir(str(versions_dir)))
            new_files = sorted(after_files - before_files)

        if not new_files:
            return jsonify({
                'success': True,
                'message': 'No schema changes detected — no new migration file created.',
                'output': output,
                'files': [],
            })

        return jsonify({
            'success': True,
            'message': f'Generated migration: {new_files[-1]}',
            'files': new_files,
            'output': output,
        })
    except Exception as exc:
        current_app.logger.exception('Autogenerate migration failed')
        return _json_error(str(exc), 500)
