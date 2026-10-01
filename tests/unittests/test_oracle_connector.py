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

    def setUp(self):
        password = patch.dict(
            os.environ,
            {'GITDATA_PASSWORD_ENV': 'PASSWORD', 'PASSWORD': 'secret'},
        )
        password.start()
        self.addCleanup(password.stop)

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

    def test_connector_accepts_explicit_sid_scheme(self):
        self.assertTrue(
            OracleConnector().accepts('oracle+sid://app@db.example/CLIENTDB')
        )

    def test_ref_resolves_connection_settings_schema_and_table(self):
        connector = OracleConnector()

        config, schema, table = connector._parts(
            'oracle://app@db.example:1522/FREEPDB1/SALES/Customers'
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
        self.assertEqual(schema, 'SALES')
        self.assertEqual(table, 'Customers')

    def test_sid_ref_resolves_connection_settings_schema_and_table(self):
        config, schema, table = OracleConnector()._parts(
            'oracle+sid://app@db.example:1522/CLIENTDB/SALES/Customers'
        )

        self.assertEqual(
            config,
            {
                'host': 'db.example',
                'port': 1522,
                'sid': 'CLIENTDB',
                'user': 'app',
                'password': 'secret',
            },
        )
        self.assertEqual(schema, 'SALES')
        self.assertEqual(table, 'Customers')

    def test_sid_ref_requires_explicit_sid(self):
        with self.assertRaisesRegex(
                ValueError, 'Oracle SID refs require an explicit SID'):
            OracleConnector()._parts('oracle+sid://app@db.example')

    def test_sid_ref_rejects_too_many_path_components_with_sid_message(self):
        with self.assertRaisesRegex(
                ValueError,
                'Oracle SID refs accept a SID, schema, and optional table path'):
            OracleConnector()._parts(
                'oracle+sid://app@db.example/CLIENTDB/SALES/table/extra'
            )

    def test_ref_infers_service_name_from_user_when_omitted(self):
        config, schema, table = OracleConnector()._parts(
            'oracle://gitdata_test@db.example'
        )

        self.assertEqual(config['service_name'], 'gitdata_test')
        self.assertEqual(config['user'], 'gitdata_test')
        self.assertTrue(config['_service_inferred'])
        self.assertIsNone(schema)
        self.assertIsNone(table)

    def test_ref_uses_schema_table_default_port_and_password_variable(self):
        config, schema, table = OracleConnector()._parts(
            'oracle://app@db.example/FREEPDB1/SALES/products'
        )

        self.assertEqual(
            config,
            {
                'host': 'db.example',
                'port': 1521,
                'service_name': 'FREEPDB1',
                'user': 'app',
                'password': 'secret',
            },
        )
        self.assertEqual(schema, 'SALES')
        self.assertEqual(table, 'products')

    def test_ref_uses_password_variable_named_by_gitdata_password_env(self):
        environment = {
            'GITDATA_PASSWORD_ENV': 'ORACLE_PASSWORD',
            'ORACLE_PASSWORD': 'custom-secret',
        }
        with patch.dict(os.environ, environment, clear=True):
            config, schema, table = OracleConnector()._parts(
                'oracle://app@db.example/FREEPDB1/SALES/products'
            )

        self.assertEqual(config['password'], 'custom-secret')
        self.assertEqual(schema, 'SALES')
        self.assertEqual(table, 'products')

    def test_ref_reports_missing_default_password_environment_variable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                    ValueError,
                    "Oracle password environment variable 'PASSWORD' is not set"):
                OracleConnector()._parts(
                    'oracle://app@db.example/FREEPDB1/products'
                )

    def test_ref_rejects_empty_gitdata_password_env(self):
        with patch.dict(
                os.environ, {'GITDATA_PASSWORD_ENV': ''}, clear=True):
            with self.assertRaisesRegex(
                    ValueError,
                    'GITDATA_PASSWORD_ENV must name an environment variable'):
                OracleConnector()._parts(
                    'oracle://app@db.example/FREEPDB1/products'
                )

    def test_ref_rejects_more_than_service_schema_and_table_path(self):
        with self.assertRaisesRegex(
                ValueError,
                'Oracle refs accept a service, schema, and optional table path'):
            OracleConnector()._parts(
                'oracle://app@db.example/FREEPDB1/SALES/products/extra'
            )

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
            'gitdata: Inline Oracle passwords are not supported; set PASSWORD '
            'or name another variable with GITDATA_PASSWORD_ENV\n',
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

    def test_ref_requires_user_and_host(self):
        refs = (
            'oracle://db.example/FREEPDB1',
            'oracle://app@/FREEPDB1',
        )
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(
                        ValueError,
                        'Oracle refs require a user and host'):
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

    def test_ref_rejects_query_parameters(self):
        refs = (
            'oracle://app@db.example/FREEPDB1?',
            'oracle://app@db.example/FREEPDB1?wallet=example',
            'oracle://app@db.example/FREEPDB1?password_env=MISSING',
        )
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(
                        ValueError,
                        'Oracle refs do not accept query parameters'):
                    OracleConnector()._parts(ref)

    def test_query_error_does_not_render_terminal_control_characters(self):
        error = StringIO()
        ref = 'oracle://app@db.example/FREEPDB1?%1B%5B31mwallet=example'

        with patch.object(sys, 'argv', ['gitdata', 'ls', ref]):
            with redirect_stderr(error):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 1)
        self.assertNotIn('\x1b', error.getvalue())
        self.assertEqual(
            error.getvalue(),
            'gitdata: Oracle refs do not accept query parameters\n',
        )

    def test_ref_rejects_fragment_table_selection(self):
        refs = (
            'oracle://app@db.example/FREEPDB1#',
            'oracle://app@db.example/FREEPDB1#customers',
        )
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(
                        ValueError,
                        'Oracle refs do not accept fragment selectors'):
                    OracleConnector()._parts(ref)

    def test_ls_lists_visible_oracle_schemas_and_closes_connection(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='db.example:1521/FREEPDB1')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([
            ('APP',),
            ('MixedCaseOwner',),
            ('Danger\x1b[31m',),
        ])
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', 'oracle://app@db.example/FREEPDB1'
            )

        self.assertEqual(
            output,
            'app\n"MixedCaseOwner"\n"Danger\\x1b[31m"\n',
        )
        self.assertNotIn('\x1b', output)
        self.assertEqual(error, '')
        driver.makedsn.assert_called_once_with(
            'db.example', 1521, service_name='FREEPDB1'
        )
        driver.connect.assert_called_once_with(
            user='app', password='secret', dsn='db.example:1521/FREEPDB1'
        )
        cursor.execute.assert_called_once_with(
            'select distinct owner from all_tables order by owner'
        )
        connection.close.assert_called_once_with()

    def test_ls_long_summarizes_visible_oracle_schemas(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')

        names_connection = MagicMock()
        names_cursor = names_connection.cursor.return_value.__enter__.return_value
        names_cursor.__iter__.return_value = iter([('SALES',)])

        stats_connection = MagicMock()
        stats_cursor = stats_connection.cursor.return_value.__enter__.return_value
        stats_cursor.__iter__.return_value = iter([('SALES', 4, 125, None)])
        driver.connect = Mock(side_effect=[names_connection, stats_connection])

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', '-l', 'oracle://app@db.example/FREEPDB1'
            )

        self.assertEqual(error, '')
        self.assertIn('Schema', output)
        self.assertIn('sales', output)
        self.assertIn('4', output)
        self.assertIn('125', output)
        stats_cursor.execute.assert_called_once_with(
            'select owner, count(*), case when count(num_rows) = count(*) '
            'then sum(num_rows) end, cast(null as number) from all_tables '
            'group by owner order by owner'
        )
        names_connection.close.assert_called_once_with()
        stats_connection.close.assert_called_once_with()

    def test_schema_summary_preserves_unknown_row_statistics(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        names_connection = MagicMock()
        stats_connection = MagicMock()
        names_cursor = names_connection.cursor.return_value.__enter__.return_value
        stats_cursor = stats_connection.cursor.return_value.__enter__.return_value
        names_cursor.__iter__.return_value = iter([('SALES',)])
        stats_cursor.__iter__.return_value = iter([('SALES', 2, None, None)])
        driver.connect = Mock(side_effect=[names_connection, stats_connection])
        with patch.dict(sys.modules, {'oracledb': driver}):
            root = OracleConnector().fetch(
                'oracle://app@db.example/FREEPDB1', count_rows=False
            )
            summaries = tuple(root['database_summaries'])

        self.assertEqual(summaries[0]['rows'], '-')
        self.assertNotIn('nvl(num_rows', stats_cursor.execute.call_args.args[0])

    def test_ls_lists_tables_visible_in_selected_oracle_schema(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([('CUSTOMERS',), ('ORDERS',)])
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', 'oracle://app@db.example/FREEPDB1/SALES'
            )

        self.assertEqual(output, 'customers\norders\n')
        self.assertEqual(error, '')
        cursor.execute.assert_called_once_with(
            'select table_name from all_tables where owner = :owner '
            'order by table_name',
            {'owner': 'SALES'},
        )
        connection.close.assert_called_once_with()

    def test_schema_root_name_uses_resolved_oracle_owner(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([('CUSTOMERS',)])
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            root = OracleConnector().fetch(
                'oracle://app@db.example/FREEPDB1/sales', count_rows=False
            )

        self.assertEqual(root['name'], 'sales')
        cursor.execute.assert_called_once_with(
            'select table_name from all_tables where owner = :owner '
            'order by table_name',
            {'owner': 'SALES'},
        )
        connection.close.assert_called_once_with()

    def test_schema_children_preserve_resolved_quoted_owner(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        names_connection = MagicMock()
        table_connection = MagicMock()
        names_cursor = names_connection.cursor.return_value.__enter__.return_value
        table_cursor = table_connection.cursor.return_value.__enter__.return_value
        names_cursor.__iter__.return_value = iter([('MixedCaseTable',)])
        table_cursor.fetchall.return_value = [
            ('ID', 'NUMBER', 'N', None, 'NO', 'NO')
        ]
        driver.connect = Mock(side_effect=[names_connection, table_connection])
        with patch.dict(sys.modules, {'oracledb': driver}):
            root = OracleConnector().fetch(
                'oracle://app@db.example/FREEPDB1/%22MixedCaseOwner%22',
                count_rows=False,
            )
            tuple(root['tables'])

        self.assertEqual(root['name'], '"MixedCaseOwner"')
        self.assertEqual(
            table_cursor.execute.call_args.args[1],
            {'owner': 'MixedCaseOwner', 'table_name': 'MixedCaseTable'},
        )

    def test_unknown_oracle_schema_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([])
        driver.connect = Mock(return_value=connection)

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle://app@db.example/FREEPDB1/missing']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle schema 'missing' has no tables visible to user "
            "'app'. Check the schema name and access permissions.\n",
        )
        connection.close.assert_called_once_with()

    def test_ls_connects_with_explicit_sid_descriptor(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='db.example:1521/CLIENTDB')
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([])
        driver.connect = Mock(return_value=connection)

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', 'oracle+sid://app@db.example/CLIENTDB'
            )

        self.assertEqual(output, '')
        self.assertEqual(error, '')
        driver.makedsn.assert_called_once_with(
            'db.example', 1521, sid='CLIENTDB'
        )
        driver.connect.assert_called_once_with(
            user='app', password='secret', dsn='db.example:1521/CLIENTDB'
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
                'oracle://app@db.example/FREEPDB1/SALES', count_rows=False
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

    def test_unreachable_oracle_sid_server_exits_with_helpful_message(self):
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
                     'oracle+sid://app@db.example/CLIENTDB']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            'gitdata: could not connect to Oracle at '
            'db.example:1521/CLIENTDB. Check the server name, confirm the '
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
            'Set PASSWORD or name another variable with '
            'GITDATA_PASSWORD_ENV.\n',
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

    def test_unknown_oracle_sid_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(full_code='ORA-12505', message='driver detail')
        driver.connect = Mock(side_effect=driver.Error(detail))

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle+sid://app@db.example/MISSING']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle SID 'MISSING' was not found at "
            'db.example:1521. Check the SID and listener registration.\n',
        )

    def test_service_error_code_is_not_translated_as_missing_sid(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(
            full_code='ORA-12514', message='service is not registered'
        )
        driver.connect = Mock(side_effect=driver.Error(detail))
        error = StringIO()

        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle+sid://app@db.example/CLIENTDB']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            'gitdata: Oracle operation failed at db.example:1521/CLIENTDB '
            '(error ORA-12514). Check the connection settings and access '
            'permissions.\n',
        )
        self.assertNotIn('was not found', error.getvalue())

    def test_wrapped_service_error_is_not_translated_as_missing_sid(self):
        config = {
            'host': 'db.example', 'port': 1521, 'sid': 'CLIENTDB',
            'user': 'app', 'password': 'secret',
        }
        detail = SimpleNamespace(
            full_code='DPY-6005',
            message='DPY-6005: failed. DPY-6001: service not registered',
        )

        translated = OracleConnector._connection_error(config, Exception(detail))

        self.assertIn('could not connect to Oracle', str(translated))
        self.assertNotIn('was not found', str(translated))

    def test_sid_error_code_does_not_change_service_error_handling(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(
            full_code='ORA-12505', message='SID is not registered'
        )
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
            'gitdata: Oracle operation failed at db.example:1521/FREEPDB1 '
            '(error ORA-12505). Check the connection settings and access '
            'permissions.\n',
        )
        self.assertNotIn('was not found', error.getvalue())

    def test_wrapped_sid_error_does_not_change_service_error_handling(self):
        config = {
            'host': 'db.example', 'port': 1521,
            'service_name': 'FREEPDB1', 'user': 'app', 'password': 'secret',
        }
        detail = SimpleNamespace(
            full_code='DPY-6005',
            message='DPY-6005: failed. DPY-6003: SID not registered',
        )

        translated = OracleConnector._connection_error(config, Exception(detail))

        self.assertIn('could not connect to Oracle', str(translated))
        self.assertNotIn('was not found', str(translated))

    def test_wrapped_unknown_oracle_sid_exits_with_helpful_message(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(
            full_code='DPY-6005',
            message=(
                'DPY-6005: cannot connect to database. '
                'DPY-6003: SID is not registered with the listener. '
                '(Similar to ORA-12505)'
            ),
        )
        driver.connect = Mock(side_effect=driver.Error(detail))

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls',
                     'oracle+sid://app@db.example/MISSING']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle SID 'MISSING' was not found at "
            'db.example:1521. Check the SID and listener registration.\n',
        )

    def test_failed_inferred_service_requests_an_explicit_service(self):
        driver = types.ModuleType('oracledb')
        driver.Error = type('Error', (Exception,), {})
        driver.makedsn = Mock(return_value='dsn')
        detail = SimpleNamespace(
            full_code='DPY-6005',
            message=(
                'DPY-6005: cannot connect to database. '
                'DPY-6001: Service is not registered with the listener.'
            ),
        )
        driver.connect = Mock(side_effect=driver.Error(detail))

        error = StringIO()
        with patch.dict(sys.modules, {'oracledb': driver}):
            with patch.object(
                    sys, 'argv',
                    ['gitdata', 'ls', 'oracle://gitdata_test@db.example']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle service 'gitdata_test', inferred from user "
            "'gitdata_test', was not found at db.example:1521. Add an "
            'explicit service name to the ref.\n',
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
                'ls', 'oracle://app@db.example/FREEPDB1/SALES/customers'
            )

        self.assertEqual(output, 'id\n"DisplayName"\n')
        self.assertEqual(error, '')
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertEqual(
            [call.args[1] for call in cursor.execute.call_args_list],
            [{'owner': 'SALES', 'table_name': 'CUSTOMERS'}],
        )
        self.assertIn(
            'from all_tab_cols c', cursor.execute.call_args.args[0]
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
                'ls', '-l', 'oracle://app@db.example/FREEPDB1/APP/CUSTOMERS'
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
        self.assertIn('from all_tab_cols c', metadata_query)
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
            ('CUSTOMERS', 3, 25, None),
        ])
        driver.connect = Mock(side_effect=[names_connection, stats_connection])

        with patch.dict(sys.modules, {'oracledb': driver}):
            output, error = self.run_cli(
                'ls', '-l',
                'oracle://app@db.example/FREEPDB1/SALES'
            )

        self.assertEqual(error, '')
        self.assertIn('Table', output)
        self.assertIn('customers', output)
        self.assertIn('3', output)
        self.assertIn('25', output)
        names_connection.close.assert_called_once_with()
        stats_cursor.execute.assert_called_once_with(
            stats_cursor.execute.call_args.args[0], {'owner': 'SALES'}
        )
        self.assertIn('from all_tables t', stats_cursor.execute.call_args.args[0])
        self.assertIn(
            'left join all_tab_columns c', stats_cursor.execute.call_args.args[0]
        )
        self.assertNotIn('all_segments', stats_cursor.execute.call_args.args[0])
        stats_connection.close.assert_called_once_with()

    def test_scan_qualifies_quoted_oracle_owner_and_table(self):
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
                'oracle://app@db.example/FREEPDB1/'
                '%22MixedCaseOwner%22/%22MixedCaseTable%22'
            )

        self.assertIn(
            '"MixedCaseTable": 2 columns, at least 2 rows (sampled)', output
        )
        self.assertIn('id', output)
        self.assertIn('name', output)
        self.assertEqual(error, 'Scanning...\n')
        self.assertEqual(
            schema_cursor.execute.call_args.args[1],
            {'owner': 'MixedCaseOwner', 'table_name': 'MixedCaseTable'},
        )
        row_cursor.execute.assert_called_once_with(
            'select * from "MixedCaseOwner"."MixedCaseTable"'
        )
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
                'oracle://app@db.example/FREEPDB1/APP/DOCUMENTS'
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
                'oracle://app@db.example/FREEPDB1/APP/CUSTOMERS'
            )

        self.assertIn('customers: 1 column, 3 rows (sampled)', output)
        self.assertEqual(error, 'Scanning...\n')
        count_cursor.execute.assert_called_once_with(
            'select count(*) from "APP"."CUSTOMERS"'
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
                     'oracle://app@db.example/FREEPDB1/APP/CUSTOMERS']):
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
                     'oracle://app@db.example/FREEPDB1/APP/CUSTOMERS']):
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
                     'oracle://app@db.example/FREEPDB1/APP/missing']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle table 'missing' was not found in schema "
            "'APP'. Check the table name.\n",
        )

    def test_unknown_oracle_table_in_sid_exits_with_helpful_message(self):
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
                     'oracle+sid://app@db.example/CLIENTDB/APP/missing']):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: Oracle table 'missing' was not found in schema "
            "'APP'. Check the table name.\n",
        )


if __name__ == '__main__':
    unittest.main()
