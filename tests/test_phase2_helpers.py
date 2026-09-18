"""Phase 2 unit tests for SQL/CORS/error/redirect helpers.

Loaded from ``app/*.py`` by file path so they run without Flask (importing the
``app`` package executes ``app/__init__.py``).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / 'app'


def _load(mod_name: str, filename: str):
    path = APP_DIR / filename
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


sql_guard = _load('sql_guard', 'sql_guard.py')
cors_util = _load('cors_util', 'cors_util.py')
http_errors = _load('http_errors', 'http_errors.py')
redirect_util = _load('redirect_util', 'redirect_util.py')


class SqlGuardTests(unittest.TestCase):
    def test_select_allowed(self):
        ok, err = sql_guard.validate_query_ui_sql('SELECT id, created_at FROM users LIMIT 10')
        self.assertTrue(ok, err)

    def test_create_does_not_match_created_at(self):
        ok, err = sql_guard.validate_query_ui_sql('SELECT created_at FROM users')
        self.assertTrue(ok, err)

    def test_drop_blocked(self):
        ok, err = sql_guard.validate_query_ui_sql('DROP TABLE users')
        self.assertFalse(ok)
        self.assertIn('DROP', err)

    def test_grant_blocked(self):
        ok, err = sql_guard.validate_query_ui_sql('GRANT ALL ON *.* TO `evil`')
        self.assertFalse(ok)
        self.assertIn('GRANT', err)

    def test_select_into_outfile_blocked(self):
        ok, err = sql_guard.validate_query_ui_sql("SELECT * FROM users INTO OUTFILE '/tmp/x'")
        self.assertFalse(ok)
        self.assertIn('OUTFILE', err)

    def test_stacked_statements_blocked(self):
        ok, err = sql_guard.validate_query_ui_sql('SELECT 1; DROP TABLE users')
        self.assertFalse(ok)
        self.assertIn('Multiple', err)

    def test_ddl_in_string_literal_allowed(self):
        ok, err = sql_guard.validate_query_ui_sql(
            "SELECT * FROM notes WHERE body = 'DROP TABLE users'"
        )
        self.assertTrue(ok, err)

    def test_insert_blocked_when_read_only(self):
        ok, err = sql_guard.validate_query_ui_sql('INSERT INTO users (id) VALUES (1)')
        self.assertFalse(ok)
        self.assertIn('INSERT', err)

    def test_insert_allowed_when_dml_enabled(self):
        ok, err = sql_guard.validate_query_ui_sql(
            'INSERT INTO users (id) VALUES (1)', allow_dml=True
        )
        self.assertTrue(ok, err)

    def test_create_still_blocked_when_dml_enabled(self):
        ok, err = sql_guard.validate_query_ui_sql('CREATE TABLE t (id INT)', allow_dml=True)
        self.assertFalse(ok)

    def test_sql_literal_escapes_quotes(self):
        self.assertEqual(sql_guard.sql_literal("O'Brien"), "'O''Brien'")


class CorsUtilTests(unittest.TestCase):
    def test_default_is_localhost_list(self):
        origins = cors_util.parse_cors_origins('', production=False)
        self.assertEqual(origins, list(cors_util.LOCAL_DEFAULT_ORIGINS))
        self.assertNotEqual(origins, '*')

    def test_star_rejected_in_production(self):
        with self.assertRaises(RuntimeError):
            cors_util.parse_cors_origins('*', production=True)

    def test_explicit_allowlist(self):
        origins = cors_util.parse_cors_origins(
            'https://dash.example.com, https://dash.example.com/',
            production=True,
        )
        self.assertEqual(origins, ['https://dash.example.com'])

    def test_socketio_reads_env(self):
        env = {'SOCKETIO_CORS_ORIGINS': 'https://a.example', 'FLASK_ENV': 'production'}
        self.assertEqual(cors_util.socketio_cors_origins(env), ['https://a.example'])


class ErrorSanitizerTests(unittest.TestCase):
    def test_production_500_is_generic(self):
        payload = http_errors.client_error_payload(
            status=500, exc=RuntimeError('secret boom'), production=True
        )
        self.assertEqual(payload, {'error': http_errors.GENERIC_500})
        self.assertNotIn('boom', payload['error'])

    def test_dev_500_may_include_message(self):
        payload = http_errors.client_error_payload(
            status=500, exc=RuntimeError('secret boom'), production=False
        )
        self.assertIn('boom', payload['error'])

    def test_strips_trace_key(self):
        data, changed = http_errors.sanitize_json_error_payload(
            {'error': 'x', 'trace': 'Traceback...'}, 500, production=False
        )
        self.assertTrue(changed)
        self.assertNotIn('trace', data)

    def test_production_500_strips_and_genericizes(self):
        data, changed = http_errors.sanitize_json_error_payload(
            {'error': 'ValueError: boom', 'trace': 'Traceback...'},
            500,
            production=True,
        )
        self.assertTrue(changed)
        self.assertEqual(data['error'], http_errors.GENERIC_500)
        self.assertNotIn('trace', data)


class RedirectUtilTests(unittest.TestCase):
    def test_relative_path_ok(self):
        self.assertTrue(redirect_util.is_safe_internal_redirect('/overview'))
        self.assertTrue(redirect_util.is_safe_internal_redirect('/login?x=1'))

    def test_open_redirects_rejected(self):
        self.assertFalse(redirect_util.is_safe_internal_redirect('https://evil.example/phish'))
        self.assertFalse(redirect_util.is_safe_internal_redirect('//evil.example'))
        self.assertFalse(redirect_util.is_safe_internal_redirect('http:evil.example'))
        self.assertFalse(redirect_util.is_safe_internal_redirect('\\evil'))
        self.assertFalse(redirect_util.is_safe_internal_redirect(None))


class AddPrivilegeHelperTests(unittest.TestCase):
    def test_user_defines_add_privilege(self):
        src = (APP_DIR / 'models.py').read_text(encoding='utf-8')
        self.assertIn('def add_privilege(self, privilege', src)
        self.assertIn('self.set_privilege', src)


if __name__ == '__main__':
    unittest.main()
