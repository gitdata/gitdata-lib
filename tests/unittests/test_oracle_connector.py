"""Direct Oracle inspection through the CLI connector."""

import builtins
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
import socket
import sys
import types
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, call, patch

from gitdata.cli import main
from gitdata.connectors.common import get_connectors
from gitdata.connectors.oracle import OracleConnector


class OracleConnectorTests(unittest.TestCase):

    def run_cli(self, *arguments):
        output = StringIO()
        error = StringIO()
        with patch.object(sys, 'argv', ['gitdata'] + list(arguments)):
            with redirect_stderr(error), redirect_stdout(output):
                main()
        return output.getvalue(), error.getvalue()

    def test_connector_discovery_does_not_import_optional_driver(self):
        original_import = builtins.__import__

        def reject_oracledb(name, *args, **kwargs):
            if name == 'oracledb':
                raise AssertionError('oracledb was imported during discovery')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=reject_oracledb):
            connector_names = {
                connector.__name__ for connector in get_connectors()
            }

        self.assertIn('OracleConnector', connector_names)

    def test_ref_resolves_connection_settings_and_selected_table(self):
        connector = OracleConnector()

        with patch.dict(os.environ, {'ORACLE_PASSWORD': 'secret'}):
            config, table = connector._parts(
                'oracle://app@db.example:1522/FREEPDB1'
                '?password_env=ORACLE_PASSWORD#Customers'
            )

        self.assertEqual(
            config,
            {
                'host': 'db.example',
                'port': 1522,
                'service_name': 'FREEPDB1',
                'user': 'app',
                'password': 'secret',
            },
        )
        self.assertEqual(table, 'Customers')

    def test_ref_rejects_inline_passwords(self):
        with self.assertRaisesRegex(
                ValueError, 'Inline Oracle passwords are not supported'):
            OracleConnector()._parts(
                'oracle://app:secret@db.example/FREEPDB1'
            )

    def test_inline_password_error_has_no_traceback(self):
        error = StringIO()
        with patch.object(
                sys, 'argv',
                ['gitdata', 'ls',
                 'oracle://app:secret@db.example/FREEPDB1']):
            with redirect_stderr(error):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            'gitdata: Inline Oracle passwords are not supported; use '
            'password_env\n',
        )

    def test_debug_output_redacts_inline_password(self):
        for password in ('supersecret', 'secret word', 'secret@word'):
            with self.subTest(password=password):
                output = StringIO()
                error = StringIO()
                ref = 'oracle://app:{}@db.example/FREEPDB1'.format(password)
                with patch.object(
                        sys, 'argv', ['gitdata', '--debug', 'ls', ref]):
                    with redirect_stdout(output), redirect_stderr(error):
                        with self.assertRaises(SystemExit):
                            main()

                combined = output.getvalue() + error.getvalue()
                self.assertNotIn(password, combined)
                self.assertIn('app:***@db.example', combined)

    def test_ref_requires_user_host_and_service(self):
        refs = (
            'oracle://db.example/FREEPDB1',
            'oracle://app@/FREEPDB1',
            'oracle://app@db.example',
            'oracle://app@db.example/first/second',
        )
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(
                        ValueError,
                        'Oracle refs require a user, host, and service name'):
                    OracleConnector()._parts(ref)

    def test_malformed_oracle_ref_exits_without_a_traceback(self):
        error = StringIO()
        with patch.object(
                sys, 'argv',
                ['gitdata', 'ls', 'oracle://[invalid/FREEPDB1']):
            with redirect_stderr(error):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(error.getvalue(), 'gitdata: Oracle ref is malformed\n')

    def test_ref_rejects_unsupported_options(self):
        with self.assertRaisesRegex(
                ValueError, 'Unsupported Oracle ref option'):
            OracleConnector()._parts(
                'oracle://app@db.example/FREEPDB1?wallet=example'
            )

    def test_unsupported_option_escapes_terminal_control_characters(self):
        error = StringIO()
        ref = 'oracle://app@db.example/FREEPDB1?%1B%5B31mwallet=example'

        with patch.object(sys, 'argv', ['gitdata', 'ls', ref]):
            with redirect_stderr(error):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 1)
        self.assertNotIn('\x1b', error.getvalue())
        self.assertIn(r'\x1b[31mwallet', error.getvalue())

    def test_ref_reports_a_missing_password_environment_variable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                    ValueError,
                    "Oracle password environment variable 'MISSING' is not set"):
                OracleConnector()._parts(
                    'oracle://app@db.example/FREEPDB1?password_env=MISSING'
                )

    def test_ref_rejects_empty_or_duplicate_password_environment_options(self):
        refs = (
            'oracle://app@db.example/FREEPDB1?password_env=',
            'oracle://app@db.example/FREEPDB1?password_env=FIRST&password_env=SECOND',
        )
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(
                        ValueError,
                        'password_env must name exactly one environment variable'):
                    OracleConnector()._parts(ref)

    def test_ls_lists_oracle_tables_and_closes_connection(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='db.example:1521/FREEPDB1')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([
            ('CUSTOMERS',),
            ('MixedCaseTable',),
            ('Danger\x1b[31m',),
        ])
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', 'oracle://app@db.example/FREEPDB1'
            )

        self.assertEqual(
            output,
            'customers\n"MixedCaseTable"\n"Danger\\x1b[31m"\n',
        )
        self.assertNotIn('\x1b', output)
        self.assertEqual(error, '')
        driver.makedsn.assert_called_once_with(
            'db.example', 1521, service_name='FREEPDB1'
        )
        driver.connect.assert_called_once_with(
            user='app', password=None, dsn='db.example:1521/FREEPDB1'
        )
        cursor.execute.assert_called_once_with(
            'select table_name from user_tables order by table_name'
        )
        connection.close.assert_called_once_with()

    def test_oracle_names_distinguish_ordinary_and_quoted_identifiers(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([('FOO',), ('foo',), ('MixedName',)])
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            root = OracleConnector().fetch(
                'oracle://app@db.example/FREEPDB1', count_rows=False
            )

        self.assertEqual(root['table_names'], ('foo', '"foo"', '"MixedName"'))
        self.assertEqual(
            OracleConnector._selector_candidates('foo'), ('FOO', 'foo')
        )
        self.assertEqual(
            OracleConnector._selector_candidates('"foo"'), ('foo',)
        )

    def test_missing_optional_driver_exits_with_install_instructions(self):
        original_import = builtins.__import__

        def reject_oracledb(name, *args, **kwargs):
            if name == 'oracledb':
                raise ModuleNotFoundError(
                    "No module named 'oracledb'", name='oracledb'
                )
            return original_import(name, *args, **kwargs)

        error = StringIO()
        with patch('builtins.__import__', side_effect=reject_oracledb):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle support requires the optional dependency; "
            "install it with 'pip install gitdata-lib[oracle]'.\n",
        )

    def test_unreachable_oracle_server_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock(
            side_effect=socket.gaierror(-2, 'Name or service not known')
        )

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            'gitdata: could not connect to Oracle at '
            'db.example:1521/FREEPDB1. Check the server name, confirm the '
            'Oracle listener is running, and verify network access.\n',
        )
        self.assertNotIn('Name or service not known', error.getvalue())

    def test_oracle_authentication_failure_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(code=1017, message='driver detail')
        driver.connect = Mock(side_effect=driver.Error(detail))

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: could not authenticate Oracle user 'app' at "
            'db.example:1521/FREEPDB1. Check the user name and password.\n',
        )

    def test_missing_oracle_credentials_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(full_code='DPY-4001', message='no credentials')
        driver.connect = Mock(side_effect=driver.Error(detail))

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle credentials were not provided for user 'app'. "
            'Set password_env in the Oracle ref.\n',
        )

    def test_unknown_oracle_service_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(full_code='ORA-12514', message='driver detail')
        driver.connect = Mock(side_effect=driver.Error(detail))

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/MISSING']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle service 'MISSING' was not found at "
            'db.example:1521. Check the service name and listener '
            'registration.\n',
        )

    def test_ls_lists_columns_for_a_selected_oracle_table(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('ID', 'NUMBER', 'N', None, 'NO', 'NO'),
            ('DisplayName', 'VARCHAR2', 'Y', None, 'NO', 'NO'),
        ]
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', 'oracle://app@db.example/FREEPDB1#customers'
            )

        self.assertEqual(output, 'id\n"DisplayName"\n')
        self.assertEqual(error, '')
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertEqual(
            [call.args[1] for call in cursor.execute.call_args_list],
            [{'table_name': 'CUSTOMERS'}],
        )
        connection.close.assert_called_once_with()

    def test_ls_long_lists_oracle_column_metadata(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('ID', 'NUMBER', 'N', None, 'YES', 'NO', 'PRI',
             10, 0, None, None),
            ('NAME', 'VARCHAR2', 'Y', "'unknown'", 'NO', 'NO', '-',
             None, None, 100, 'B'),
        ]
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', '-l', 'oracle://app@db.example/FREEPDB1#CUSTOMERS'
            )

        self.assertEqual(error, '')
        self.assertIn('Column', output)
        self.assertIn('Type', output)
        self.assertIn('id', output)
        self.assertIn('NUMBER(10)', output)
        self.assertIn('VARCHAR2(100)', output)
        self.assertIn('IDENTITY', output)
        self.assertIn('PRI', output)
        self.assertIn("'unknown'", output)
        metadata_query = cursor.execute.call_args.args[0]
        self.assertIn('from user_tab_cols c', metadata_query)
        self.assertIn("c.user_generated = 'YES'", metadata_query)

    def test_ls_long_lists_oracle_table_metadata(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')

        names_connection = MagicMock()
        names_cursor = names_connection.cursor.return_value.__enter__.return_value
        names_cursor.__iter__.return_value = iter([('CUSTOMERS',)])

        stats_connection = MagicMock()
        stats_cursor = stats_connection.cursor.return_value.__enter__.return_value
        stats_cursor.__iter__.return_value = iter([
            ('CUSTOMERS', 3, 25, 1),
        ])
        driver.connect = Mock(side_effect=[names_connection, stats_connection])

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', '-l', 'oracle://app@db.example/FREEPDB1'
            )

        self.assertEqual(error, '')
        self.assertIn('Table', output)
        self.assertIn('customers', output)
        self.assertIn('3', output)
        self.assertIn('25', output)
        self.assertIn('1', output)
        names_connection.close.assert_called_once_with()
        stats_connection.close.assert_called_once_with()

    def test_scan_streams_selected_oracle_table_and_closes_resources(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')

        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.fetchall.return_value = [
            ('ID', 'NUMBER', 'N', None, 'NO', 'NO'),
            ('NAME', 'VARCHAR2', 'Y', None, 'NO', 'NO'),
        ]

        row_connection = MagicMock()
        row_cursor = row_connection.cursor.return_value
        row_cursor.__iter__.return_value = iter([
            (1, 'one'),
            (2, 'two'),
            (3, 'three'),
        ])
        driver.connect = Mock(side_effect=[schema_connection, row_connection])

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'scan', '--no-count', '--limit', '2',
                'oracle://app@db.example/FREEPDB1#customers'
            )

        self.assertIn('customers: 2 columns, at least 2 rows (sampled)', output)
        self.assertIn('id', output)
        self.assertIn('name', output)
        self.assertEqual(error, 'Scanning...\n')
        row_cursor.execute.assert_called_once_with('select * from "CUSTOMERS"')
        row_cursor.close.assert_called_once_with()
        row_connection.close.assert_called_once_with()

    def test_scan_materializes_oracle_lobs_before_closing_connection(self):
        class FakeLOB:
            def __init__(self, value):
                self.value = value
                self.read_args = None

            def read(self, offset, amount):
                self.read_args = (offset, amount)
                return self.value[:amount]

        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.LOB = FakeLOB
        driver.makedsn = Mock(return_value='dsn')

        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.fetchall.return_value = [
            ('CONTENTS', 'CLOB', 'Y', None, 'NO', 'NO'),
        ]

        lob = FakeLOB('stored text')
        row_connection = MagicMock()
        row_cursor = row_connection.cursor.return_value
        row_cursor.__iter__.return_value = iter([(lob,)])
        driver.connect = Mock(side_effect=[schema_connection, row_connection])

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'scan', '--no-count', '--limit', '1',
                'oracle://app@db.example/FREEPDB1#DOCUMENTS'
            )

        self.assertEqual(lob.read_args, (1, 4096))
        self.assertIn('stored text', output)
        self.assertEqual(error, 'Scanning...\n')
        row_connection.close.assert_called_once_with()

    def test_scan_counts_oracle_rows_by_default(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')

        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.fetchall.return_value = [
            ('ID', 'NUMBER', 'N', None, 'NO', 'NO'),
        ]

        count_connection = MagicMock()
        count_cursor = count_connection.cursor.return_value.__enter__.return_value
        count_cursor.fetchone.return_value = (3,)

        row_connection = MagicMock()
        row_cursor = row_connection.cursor.return_value
        row_cursor.__iter__.return_value = iter([(1,), (2,), (3,)])
        driver.connect = Mock(side_effect=[
            schema_connection,
            count_connection,
            row_connection,
        ])

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'scan', '--limit', '2',
                'oracle://app@db.example/FREEPDB1#CUSTOMERS'
            )

        self.assertIn('customers: 1 column, 3 rows (sampled)', output)
        self.assertEqual(error, 'Scanning...\n')
        count_cursor.execute.assert_called_once_with(
            'select count(*) from "CUSTOMERS"'
        )
        count_connection.close.assert_called_once_with()

    def test_oracle_metadata_failure_exits_cleanly_and_closes_connection(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        detail = SimpleNamespace(
            full_code='ORA-01031', message='private permission detail'
        )
        cursor.execute.side_effect = driver.Error(detail)
        driver.connect = Mock(return_value=connection)

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn('Oracle operation failed', error.getvalue())
        self.assertIn('ORA-01031', error.getvalue())
        self.assertNotIn('private permission detail', error.getvalue())
        connection.close.assert_called_once_with()

    def test_oracle_cleanup_failure_exits_without_a_traceback(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([])
        detail = SimpleNamespace(
            full_code='DPY-4011', message='private cleanup failure'
        )
        connection.close.side_effect = driver.Error(detail)
        driver.connect = Mock(return_value=connection)

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn('Oracle operation failed', error.getvalue())
        self.assertNotIn('private cleanup failure', error.getvalue())

    def test_oracle_row_failure_exits_cleanly_and_closes_resources(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')

        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.fetchall.return_value = [
            ('ID', 'NUMBER', 'N', None, 'NO', 'NO'),
        ]

        row_connection = MagicMock()
        row_cursor = row_connection.cursor.return_value
        detail = SimpleNamespace(
            full_code='DPY-4011', message='private row failure detail'
        )
        row_cursor.__iter__.side_effect = driver.Error(detail)
        driver.connect = Mock(side_effect=[schema_connection, row_connection])

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'scan', '--no-count',
                     'oracle://app@db.example/FREEPDB1#CUSTOMERS']):
                with redirect_stderr(error), redirect_stdout(StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn('Oracle operation failed', error.getvalue())
        self.assertNotIn('private row failure detail', error.getvalue())
        row_cursor.close.assert_called_once_with()
        row_connection.close.assert_called_once_with()

    def test_oracle_cursor_failure_closes_row_connection(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')

        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.fetchall.return_value = [
            ('ID', 'NUMBER', 'N', None, 'NO', 'NO'),
        ]

        row_connection = MagicMock()
        detail = SimpleNamespace(full_code='DPY-4011', message='cursor failure')
        row_connection.cursor.side_effect = driver.Error(detail)
        driver.connect = Mock(side_effect=[schema_connection, row_connection])

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'scan', '--no-count',
                     'oracle://app@db.example/FREEPDB1#CUSTOMERS']):
                with redirect_stderr(error), redirect_stdout(StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn('Oracle operation failed', error.getvalue())
        row_connection.close.assert_called_once_with()

    def test_unknown_oracle_table_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [[], []]
        driver.connect = Mock(return_value=connection)

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1#missing']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle table 'missing' was not found in service "
            "'FREEPDB1'. Check the table name.\n",
        )


if __name__ == '__main__':
    unittest.main()
