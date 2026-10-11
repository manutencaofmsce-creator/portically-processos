"""Synthetic probes only; never import production data or send mail."""
import os
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import psycopg
import app
import health_app_V1  # Registers safe probes on the existing application.
import health_checks_V1 as probes


def settings(**changes):
    result = dict(DATABASE_URL='postgresql://synthetic.invalid/test',
                  DATA_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                  DATA_HMAC_KEY='d' * 32, AUTHORIZED_EMAIL='test@example.invalid',
                  SESSION_SECRET='s' * 32, RESEND_API_KEY='synthetic',
                  RESEND_FROM_EMAIL='test@example.invalid', NEW_CASE={})
    result.update(changes)
    return result


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.config = settings()
        self.connection = MagicMock()
        self.cursor = self.connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = (1,)
        self.connect_patch = patch.object(probes.psycopg, 'connect', return_value=self.connection)
        self.connect = self.connect_patch.start()
        self.addCleanup(self.connect_patch.stop)

    def test_available_database_is_ready_without_reading_rows(self):
        response = probes.readiness_response(self.config)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b'{"status":"ready"}')
        queries = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertEqual(len(queries), 1 + len(probes.BASE_TABLES + probes.PROCESS_TABLES))
        self.assertTrue(all(query.endswith('LIMIT 0') for query in queries[1:]))
        self.cursor.fetchone.assert_called_once()
        self.assertNotIn('COUNT', ''.join(queries))

    def test_connection_failure_is_503_without_secrets(self):
        self.connect.side_effect = psycopg.OperationalError('password=PROTECTED host=PROTECTED')
        response = probes.readiness_response(self.config)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.body, b'{"status":"not-ready"}')
        self.assertIn('no-store', response.headers['cache-control'])

    def test_connection_interrupted_during_query_is_503(self):
        self.cursor.execute.side_effect = psycopg.OperationalError('connection lost')
        self.assertEqual(probes.readiness_response(self.config).status_code, 503)

    def test_each_required_configuration_field_is_checked_before_connecting(self):
        for name in ('DATABASE_URL', 'DATA_ENCRYPTION_KEY', 'DATA_HMAC_KEY',
                     'AUTHORIZED_EMAIL', 'SESSION_SECRET', 'RESEND_API_KEY', 'RESEND_FROM_EMAIL'):
            with self.subTest(name=name):
                self.assertEqual(probes.readiness_response(settings(**{name: ' '})).status_code, 503)
        self.connect.assert_not_called()

    def test_invalid_encryption_key_is_503(self):
        self.assertFalse(probes.is_ready(settings(DATA_ENCRYPTION_KEY='invalid')))
        self.connect.assert_not_called()

    def test_each_table_missing_is_503(self):
        for table in probes.BASE_TABLES + probes.PROCESS_TABLES + probes.OTP_TABLES + ('protected_case_bundles',):
            with self.subTest(table=table):
                def execute(sql):
                    if f'"{table}"' in sql:
                        raise psycopg.errors.UndefinedTable('PROTECTED')
                self.cursor.execute.side_effect = execute
                self.assertFalse(probes.is_ready(settings(otp_service=object(), OTP_HMAC_KEY='o' * 32, CaseStore=object())))

    def test_read_permission_failure_is_503(self):
        self.cursor.execute.side_effect = psycopg.errors.InsufficientPrivilege('PROTECTED')
        self.assertFalse(probes.is_ready(self.config))

    def test_statement_timeout_is_503(self):
        self.cursor.execute.side_effect = psycopg.errors.QueryCanceled('PROTECTED')
        self.assertFalse(probes.is_ready(self.config))

    def test_unexpected_select_result_is_503(self):
        self.cursor.fetchone.return_value = None
        self.assertFalse(probes.is_ready(self.config))

    def test_timeouts_and_read_only_override_dsn_options(self):
        self.assertTrue(probes.is_ready(self.config))
        self.assertEqual(self.connect.call_args.kwargs['connect_timeout'], 3)
        self.assertEqual(self.connect.call_args.kwargs['options'], '-c statement_timeout=1000 -c default_transaction_read_only=on')
        self.connection.__exit__.assert_called_once()

    def test_v21_v22_and_combined_profiles(self):
        for features in ({}, {'otp_service': object()}, {'CaseStore': object()},
                         {'otp_service': object(), 'CaseStore': object()}):
            with self.subTest(features=list(features)):
                self.cursor.reset_mock()
                self.cursor.fetchone.return_value = (1,)
                self.assertTrue(probes.is_ready(settings(OTP_HMAC_KEY='o' * 32, **features)))
                queries = ' '.join(call.args[0] for call in self.cursor.execute.call_args_list)
                self.assertEqual('auth_otp_challenges' in queries, 'otp_service' in features)
                self.assertEqual('protected_case_bundles' in queries, 'CaseStore' in features)

    def test_v21_requires_valid_secret_lengths(self):
        for changes in ({'OTP_HMAC_KEY': ''}, {'OTP_HMAC_KEY': 'short'}, {'SESSION_SECRET': 'short'}):
            with self.subTest(changes=list(changes)):
                self.assertFalse(probes.is_ready(settings(otp_service=object(), OTP_HMAC_KEY='o' * 32) | changes))
        self.connect.assert_not_called()

    def test_legacy_profile_does_not_require_later_process_tables(self):
        del self.config['NEW_CASE']
        self.assertTrue(probes.is_ready(self.config))
        self.assertEqual(self.cursor.execute.call_count, 3)

    def test_http_routes_are_public_generic_and_do_not_deliver_mail(self):
        client = TestClient(app.app)  # No lifespan: never run application initialization.
        with ExitStack() as stack:
            for key, value in (self.config | {'OTP_HMAC_KEY': 'o' * 32}).items():
                stack.enter_context(patch.object(app, key, value, create=True))
            send = stack.enter_context(patch.object(app, 'send_otp'))
            for route in ('/health', '/live'):
                self.connect.reset_mock()
                response = client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'status': 'ok'})
                self.assertIn('no-store', response.headers['cache-control'])
                self.connect.assert_not_called()
            response = client.get('/ready')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'status': 'ready'})
            self.connect.side_effect = psycopg.OperationalError('PROTECTED')
            response = client.get('/ready')
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {'status': 'not-ready'})
            self.assertIn('no-store', response.headers['cache-control'])
            self.assertEqual(client.get('/health').status_code, 200)
            send.assert_not_called()


@unittest.skipUnless(os.environ.get('TEST_HEALTH_DATABASE_URL'), 'isolated PostgreSQL not configured')
class PostgreSQLReadinessTests(unittest.TestCase):
    def test_real_tables_missing_permissions_and_connection_failure(self):
        # Dedicated disposable database only. No application initialization or data.
        url = os.environ['TEST_HEALTH_DATABASE_URL']
        config = settings(DATABASE_URL=url, OTP_HMAC_KEY='o' * 32, otp_service=object(), CaseStore=object())
        tables = probes.BASE_TABLES + probes.PROCESS_TABLES + probes.OTP_TABLES + ('protected_case_bundles',)
        with psycopg.connect(url, autocommit=True) as conn:
            existing = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'").fetchone()[0]
            self.assertEqual(existing, 0, 'Integration test requires an empty disposable database')
            try:
                self.assertFalse(probes.is_ready(config))
                for table in tables:
                    conn.execute(f'CREATE TABLE public."{table}" (synthetic_id integer)')
                self.assertTrue(probes.is_ready(config))
                for table in tables:
                    conn.execute(f'DROP TABLE public."{table}"')
                    self.assertFalse(probes.is_ready(config))
                    conn.execute(f'CREATE TABLE public."{table}" (synthetic_id integer)')
                # Real lock timeout: SELECT LIMIT 0 must fail within statement_timeout.
                with psycopg.connect(url) as locker:
                    locker.execute('LOCK TABLE public.radar_items IN ACCESS EXCLUSIVE MODE')
                    self.assertFalse(probes.is_ready(config))
                self.assertTrue(probes.is_ready(config))
                self.assertFalse(probes.is_ready(config | {'DATABASE_URL': 'postgresql://test:test@127.0.0.1:1/test'}))
            finally:
                for table in tables:
                    conn.execute(f'DROP TABLE IF EXISTS public."{table}"')


if __name__ == '__main__':
    unittest.main()
