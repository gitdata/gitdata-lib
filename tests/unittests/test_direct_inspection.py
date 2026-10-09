"""Direct inspection of rooted Connector output."""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, patch

import pymysql

from gitdata.cli import main
from gitdata.connectors import common, fetch
from gitdata.connectors.common import BaseConnector, get_connectors
from gitdata.connectors.tabular import (
    CsvConnector,
    MariaDBConnector,
    SQLiteConnector,
)
from gitdata.inspection import list_items, scan


class DirectInspectionTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        password = patch.dict(
            os.environ,
            {'GITDATA_PASSWORD_ENV': 'PASSWORD', 'PASSWORD': 'secret'},
        )
        password.start()
        self.addCleanup(password.stop)

    def write_csv(self, name, text):
        pathname = os.path.join(self.tempdir.name, name)
        with open(pathname, 'w', encoding='utf-8', newline='') as output:
            output.write(text)
        return pathname

    def run_cli(self, *arguments):
        output = StringIO()
        with patch.object(sys, 'argv', ['gitdata'] + list(arguments)):
            with redirect_stderr(StringIO()):
                with redirect_stdout(output):
                    main()
        return output.getvalue()

    def test_mysql_unknown_server_exits_with_helpful_message(self):
        error = StringIO()
        connection_error = pymysql.err.OperationalError(
            2003,
            "Can't connect to MySQL server on 'myserver' "
            '([Errno -2] Name or service not known)',
        )

        with patch.object(
                sys, 'argv', ['gitdata', 'ls', 'mysql://myserver']):
            with patch(
                    'gitdata.connectors.tabular.pymysql.connect',
                    side_effect=connection_error):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            'gitdata: could not connect to MySQL server at myserver:3306. '
            'Check the server name, confirm MySQL is running, and verify '
            'network access.\n',
        )

    def test_mysql_unknown_server_escapes_host_name(self):
        error = StringIO()
        connection_error = pymysql.err.OperationalError(2003, 'unreachable')

        with patch.object(
                sys, 'argv', ['gitdata', 'ls', 'mysql://\x1bredhost']):
            with patch(
                    'gitdata.connectors.tabular.pymysql.connect',
                    side_effect=connection_error):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit):
                        main()

        self.assertIn('MySQL server at \\x1bredhost:3306', error.getvalue())
        self.assertNotIn('\x1b', error.getvalue())

    def test_mysql_authentication_failure_exits_with_helpful_message(self):
        error = StringIO()
        connection_error = pymysql.err.OperationalError(
            1045,
            "Access denied for user 'root'@'client' (using password: YES)",
        )

        with patch.object(
                sys, 'argv', ['gitdata', 'ls', 'mysql://root@db.example']):
            with patch(
                    'gitdata.connectors.tabular.pymysql.connect',
                    side_effect=connection_error):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: could not authenticate MySQL user 'root' at "
            'db.example:3306. Check the user name and password.\n',
        )
        self.assertNotIn('using password', error.getvalue())

    def test_mysql_authentication_failure_escapes_user_name(self):
        error = StringIO()
        connection_error = pymysql.err.OperationalError(1045, 'access denied')

        with patch.object(
                sys, 'argv',
                ['gitdata', 'ls', 'mysql://bad%1b%5b31m@db.example']):
            with patch(
                    'gitdata.connectors.tabular.pymysql.connect',
                    side_effect=connection_error):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit):
                        main()

        self.assertEqual(
            error.getvalue(),
            "gitdata: could not authenticate MySQL user 'bad\\x1b[31m' at "
            'db.example:3306. Check the user name and password.\n',
        )
        self.assertNotIn('\x1b', error.getvalue())

    def test_mysql_unknown_database_exits_with_helpful_message(self):
        error = StringIO()
        connection_error = pymysql.err.OperationalError(
            1049, "Unknown database 'missing'"
        )

        with patch.object(
                sys, 'argv',
                ['gitdata', 'ls', 'mysql://root@db.example/missing']):
            with patch(
                    'gitdata.connectors.tabular.pymysql.connect',
                    side_effect=connection_error):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            "gitdata: MySQL database 'missing' was not found at "
            'db.example:3306. Check the database name.\n',
        )

    def test_mysql_other_connection_failure_hides_driver_details(self):
        error = StringIO()
        connection_error = pymysql.err.OperationalError(
            9999, 'driver detail that should not reach the terminal'
        )

        with patch.object(
                sys, 'argv', ['gitdata', 'ls', 'mysql://db.example']):
            with patch(
                    'gitdata.connectors.tabular.pymysql.connect',
                    side_effect=connection_error):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            error.getvalue(),
            'gitdata: MySQL could not open a connection to db.example:3306 '
            '(error 9999). Check the server settings and access permissions.\n',
        )
        self.assertNotIn('driver detail', error.getvalue())

    def test_ctrl_c_exits_cleanly_without_a_traceback(self):
        error = StringIO()
        with patch.object(sys, 'argv', ['gitdata', 'scan', 'slow.csv']):
            with patch(
                    'gitdata.cli.gitdata_scan.scan_to_console',
                    side_effect=KeyboardInterrupt):
                with redirect_stderr(error):
                    with self.assertRaises(SystemExit) as raised:
                        main()

        self.assertEqual(raised.exception.code, 130)
        self.assertEqual(error.getvalue(), '\nInterrupted.\n')

    def test_ctrl_c_during_a_scan_closes_rows_and_exits_cleanly(self):
        closed = []

        def rows():
            try:
                raise KeyboardInterrupt
                yield
            finally:
                closed.append(True)

        root = {
            'type': 'table',
            'name': 'slow',
            'columns': ('value',),
            'rows': rows(),
        }
        error = StringIO()
        with patch.object(sys, 'argv', ['gitdata', 'scan', 'slow.csv']):
            with patch(
                    'gitdata.cli.gitdata_scan.fetch',
                    return_value=root):
                with redirect_stderr(error):
                    with redirect_stdout(StringIO()):
                        with self.assertRaises(SystemExit) as raised:
                            main()

        self.assertEqual(raised.exception.code, 130)
        self.assertEqual(closed, [True])
        self.assertEqual(error.getvalue(), 'Scanning...\n\nInterrupted.\n')

    def test_tabular_connectors_participate_in_connector_discovery(self):
        connector_types = set(get_connectors())

        self.assertTrue(issubclass(CsvConnector, BaseConnector))
        self.assertTrue(issubclass(MariaDBConnector, BaseConnector))
        self.assertTrue(issubclass(SQLiteConnector, BaseConnector))
        self.assertIn(CsvConnector, connector_types)
        self.assertIn(MariaDBConnector, connector_types)
        self.assertIn(SQLiteConnector, connector_types)

    def test_fetch_keeps_legacy_connector_signatures_compatible(self):
        class LegacyConnector(BaseConnector):
            def fetch(self, ref):
                if ref == 'legacy':
                    return {'type': 'column', 'name': 'legacy'}
                return None

        with patch.object(
                common,
                'get_connectors',
                return_value=(LegacyConnector,)):
            root = common.fetch('legacy', count_rows=False)

        self.assertEqual(root, {'type': 'column', 'name': 'legacy'})

    def test_mariadb_rows_use_an_unbuffered_cursor(self):
        self.assertIs(
            MariaDBConnector.row_cursor_class,
            pymysql.cursors.SSCursor,
        )

    def test_mariadb_table_exposes_an_eager_count_query(self):
        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.__iter__.return_value = iter([('customer_id',), ('name',)])
        count_connection = MagicMock()
        count_cursor = count_connection.cursor.return_value.__enter__.return_value
        count_cursor.fetchone.return_value = (23,)
        connector = MariaDBConnector()

        with patch.object(
                connector,
                '_connect',
                side_effect=(schema_connection, count_connection)):
            table = connector._table(
                {'database': 'cocal'}, 'customers', count_rows=True
            )

        self.assertEqual(table['row_count'], 23)
        count_cursor.execute.assert_called_once_with(
            'select count(*) from `customers`'
        )
        count_connection.close.assert_called_once_with()

    def test_mariadb_table_can_skip_the_eager_count_query(self):
        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.__iter__.return_value = iter([('customer_id',)])
        connector = MariaDBConnector()

        with patch.object(
                connector,
                '_connect',
                return_value=schema_connection) as connect:
            table = connector._table(
                {'database': 'cocal'}, 'customers', count_rows=False
            )

        self.assertIsNone(table['row_count'])
        connect.assert_called_once_with({'database': 'cocal'})

    def test_mariadb_connection_closes_if_read_only_setup_fails(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = RuntimeError('read-only setup failed')

        with patch(
                'gitdata.connectors.tabular.pymysql.connect',
                return_value=connection):
            with self.assertRaisesRegex(RuntimeError, 'read-only setup failed'):
                MariaDBConnector._connect({})

        connection.close.assert_called_once_with()

    def test_mariadb_connection_closes_if_read_only_setup_is_interrupted(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = KeyboardInterrupt

        with patch(
                'gitdata.connectors.tabular.pymysql.connect',
                return_value=connection):
            with self.assertRaises(KeyboardInterrupt):
                MariaDBConnector._connect({})

        connection.close.assert_called_once_with()

    def test_mysql_server_ref_lists_visible_databases(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([
            ('gitdata_example',),
            ('information_schema',),
        ])

        with patch(
                'gitdata.connectors.tabular.pymysql.connect',
                return_value=connection) as connect:
            output = self.run_cli('ls', 'mysql://root@127.0.0.1')

        self.assertEqual(output, 'gitdata_example\n')
        connect.assert_called_once_with(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='secret',
            charset='utf8mb4',
            autocommit=True,
        )
        cursor.execute.assert_any_call('show databases')
        connection.close.assert_called_once_with()

    def test_mysql_server_all_lists_system_databases(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([
            ('gitdata_example',),
            ('performance_schema',),
        ])

        with patch(
                'gitdata.connectors.tabular.pymysql.connect',
                return_value=connection):
            output = self.run_cli('ls', '-a', 'mysql://root@127.0.0.1')

        self.assertEqual(output, 'gitdata_example\nperformance_schema\n')

    def test_mysql_server_verbose_lists_database_stats(self):
        names_connection = MagicMock()
        names_cursor = names_connection.cursor.return_value.__enter__.return_value
        names_cursor.__iter__.return_value = iter([('cocal',)])
        stats_connection = MagicMock()
        stats_cursor = stats_connection.cursor.return_value.__enter__.return_value
        stats_cursor.__iter__.return_value = iter([('cocal', 3, 42, 7)])

        with patch.object(
                MariaDBConnector,
                '_connect',
                side_effect=(names_connection, stats_connection)):
            output = self.run_cli('ls', '-l', 'mysql://root@localhost')

        self.assertIn('Database', output)
        self.assertRegex(output, r'cocal\s+3\s+42\s+7')
        lines = output.splitlines()
        self.assertEqual(
            lines[0],
            '{} {} {} {}'.format(
                'Database'.ljust(35),
                'Tables'.rjust(10),
                'Rows'.rjust(15),
                'Size (MB)'.rjust(10),
            ),
        )
        self.assertEqual(
            lines[2],
            '{} {} {} {}'.format(
                'cocal'.ljust(35),
                '3'.rjust(10),
                '42'.rjust(15),
                '7'.rjust(10),
            ),
        )
        stats_cursor.execute.assert_called_once()
        stats_sql = stats_cursor.execute.call_args[0][0].lower()
        self.assertIn("t.table_type='base table'", stats_sql)
        self.assertIn('s.schema_name not in', stats_sql)
        stats_connection.close.assert_called_once_with()

    def test_mysql_server_long_all_includes_system_database_stats(self):
        names_connection = MagicMock()
        names_cursor = names_connection.cursor.return_value.__enter__.return_value
        names_cursor.__iter__.return_value = iter([('performance_schema',)])
        stats_connection = MagicMock()
        stats_cursor = stats_connection.cursor.return_value.__enter__.return_value
        stats_cursor.__iter__.return_value = iter([
            ('performance_schema', 12, 0, 0),
        ])

        with patch.object(
                MariaDBConnector,
                '_connect',
                side_effect=(names_connection, stats_connection)):
            output = self.run_cli('ls', '-la', 'mysql://root@localhost')

        self.assertRegex(output, r'performance_schema\s+12\s+0\s+0')
        stats_sql = stats_cursor.execute.call_args[0][0].lower()
        self.assertNotIn('s.schema_name not in', stats_sql)

    def test_mysql_server_ref_defaults_to_current_os_user(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([])

        with patch(
                'gitdata.connectors.tabular.pymysql.connect',
                return_value=connection) as connect:
            with patch(
                    'getpass.getuser',
                    return_value='lab-user'):
                self.run_cli('ls', 'mysql://zeno')

        connect.assert_called_once_with(
            host='zeno',
            port=3306,
            user='lab-user',
            password='secret',
            charset='utf8mb4',
            autocommit=True,
        )

    def test_mysql_database_verbose_lists_table_stats(self):
        names_connection = MagicMock()
        names_cursor = names_connection.cursor.return_value.__enter__.return_value
        names_cursor.__iter__.return_value = iter([('customers',)])
        stats_connection = MagicMock()
        stats_cursor = stats_connection.cursor.return_value.__enter__.return_value
        stats_cursor.__iter__.return_value = iter([('customers', 5, 23, 2)])

        with patch.object(
                MariaDBConnector,
                '_connect',
                side_effect=(names_connection, stats_connection)):
            output = self.run_cli(
                'ls', '-l', 'mysql://root@localhost/cocal'
            )

        self.assertIn('Table', output)
        self.assertRegex(output, r'customers\s+5\s+23\s+2')
        stats_cursor.execute.assert_called_once()
        stats_connection.close.assert_called_once_with()

    def test_mysql_table_verbose_lists_columns_and_indexes(self):
        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.__iter__.return_value = iter([('id',), ('name',)])
        detail_connection = MagicMock()
        detail_cursor = detail_connection.cursor.return_value.__enter__.return_value
        detail_cursor.__iter__.return_value = iter([
            ('id', 'int', 'NO', 'PRI', None, 'auto_increment'),
            ('name', 'varchar(80)', 'YES', '', None, ''),
        ])
        index_connection = MagicMock()
        index_cursor = index_connection.cursor.return_value.__enter__.return_value
        index_cursor.__iter__.return_value = iter([
            ('customers', 0, 'PRIMARY', 1, 'id'),
        ])

        with patch.object(
                MariaDBConnector,
                '_connect',
                side_effect=(
                    schema_connection,
                    detail_connection,
                    index_connection,
                )):
            output = self.run_cli(
                'ls', '-l', 'mysql://root@localhost/cocal.customers'
            )

        self.assertRegex(output, r'id\s+int\s+NO\s+PRI\s+-\s+auto_increment')
        self.assertRegex(output, r'name\s+varchar\(80\)\s+YES')
        self.assertRegex(output, r'PRIMARY\s+YES\s+id')

    def test_mysql_table_verbose_handles_functional_indexes(self):
        schema_connection = MagicMock()
        schema_cursor = schema_connection.cursor.return_value.__enter__.return_value
        schema_cursor.__iter__.return_value = iter([('name',)])
        detail_connection = MagicMock()
        detail_cursor = detail_connection.cursor.return_value.__enter__.return_value
        detail_cursor.__iter__.return_value = iter([
            ('name', 'varchar(80)', 'YES', '', None, ''),
        ])
        index_connection = MagicMock()
        index_cursor = index_connection.cursor.return_value.__enter__.return_value
        index_cursor.__iter__.return_value = iter([
            ('customers', 1, 'name_lower', 1, None, None, 0, None,
             None, 'YES', 'BTREE', '', '', 'YES', 'lower(`name`)'),
        ])

        with patch.object(
                MariaDBConnector,
                '_connect',
                side_effect=(
                    schema_connection,
                    detail_connection,
                    index_connection,
                )):
            output = self.run_cli(
                'ls', '-l', 'mysql://root@localhost/cocal.customers'
            )

        self.assertRegex(output, r'name_lower\s+NO\s+lower\(`name`\)')

    def test_mysql_ref_accepts_database_dot_table_selection(self):
        config, table = MariaDBConnector()._parts(
            'mysql://localhost/cocal.cal_event'
        )

        self.assertEqual(config['database'], 'cocal')
        self.assertEqual(table, 'cal_event')

    def test_mysql_ref_rejects_fragment_table_selection(self):
        refs = (
            'mysql://localhost/cocal#',
            'mysql://localhost/cocal#cal_event',
            'mysql://localhost/archive.2026#cal_event',
        )
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(
                        ValueError,
                        'MariaDB refs do not accept fragment selectors'):
                    MariaDBConnector()._parts(ref)

    def test_mysql_ref_preserves_encoded_dot_in_database_name(self):
        config, table = MariaDBConnector()._parts(
            'mysql://localhost/archive%2E2026'
        )

        self.assertEqual(config['database'], 'archive.2026')
        self.assertIsNone(table)

    def test_mysql_ref_rejects_extra_path_segments_after_dotted_table(self):
        with self.assertRaisesRegex(ValueError, 'database and table'):
            MariaDBConnector()._parts(
                'mysql://localhost/cocal.cal_event/extra'
            )

    def test_mysql_ref_rejects_query_parameters(self):
        refs = (
            'mysql://localhost/cocal?',
            'mysql://localhost/cocal?password_env=MYSQL_PASSWORD',
        )
        for ref in refs:
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(
                        ValueError,
                        'MariaDB refs do not accept query parameters'):
                    MariaDBConnector()._parts(ref)

    def test_mysql_ref_uses_password_named_by_gitdata_password_env(self):
        environment = {
            'GITDATA_PASSWORD_ENV': 'MYSQL_PASSWORD',
            'MYSQL_PASSWORD': 'custom-secret',
        }
        with patch.dict(os.environ, environment, clear=True):
            config, _ = MariaDBConnector()._parts(
                'mysql://root@localhost/cocal'
            )

        self.assertEqual(config['password'], 'custom-secret')

    def test_mysql_ref_reports_missing_default_password_variable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                    ValueError,
                    "MariaDB password environment variable 'PASSWORD' is not set"):
                MariaDBConnector()._parts('mysql://root@localhost/cocal')

    def test_mariadb_inline_passwords_are_rejected_without_echoing_them(self):
        password = '-'.join(('not', 'for', 'logs'))
        ref = 'mysql://root:{}@127.0.0.1/gitdata_example'.format(password)

        with self.assertRaisesRegex(
                ValueError, 'GITDATA_PASSWORD_ENV') as raised:
            MariaDBConnector()._parts(ref)

        self.assertNotIn(password, str(raised.exception))

    def test_csv_ref_is_listed_and_scanned_without_a_store(self):
        pathname = self.write_csv(
            'customers.csv',
            'id,name,active\n1,Ada,true\n2,Grace,false\n3,Linus,true\n',
        )

        root = fetch(pathname)

        self.assertEqual(root['type'], 'table')
        self.assertEqual(root['name'], 'customers.csv')
        self.assertEqual(root['columns'], ('id', 'name', 'active'))
        self.assertNotIsInstance(root['rows'], (list, tuple))
        self.assertEqual(list_items(root), [
            {'name': 'id', 'type': 'column'},
            {'name': 'name', 'type': 'column'},
            {'name': 'active', 'type': 'column'},
        ])

        reports = scan(fetch(pathname), limit=100)

        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertEqual(report['name'], 'customers.csv')
        self.assertEqual(report['row_count'], 3)
        self.assertEqual(report['rows_scanned'], 3)
        self.assertFalse(report['sampled'])
        self.assertEqual(report['columns'], [
            {
                'name': 'id',
                'data_types': ('string',),
                'cardinality': 3,
                'max_width': 1,
                'observed': ('1', '2', '3'),
            },
            {
                'name': 'name',
                'data_types': ('string',),
                'cardinality': 3,
                'max_width': 5,
                'observed': ('Ada', 'Grace', 'Linus'),
            },
            {
                'name': 'active',
                'data_types': ('string',),
                'cardinality': 2,
                'max_width': 5,
                'observed': ('true', 'false'),
            },
        ])

    def test_csv_duplicate_column_names_do_not_collapse_values(self):
        pathname = self.write_csv(
            'duplicate-columns.csv',
            'id,id\n1,2\n',
        )

        report = scan(fetch(pathname))[0]

        self.assertEqual(report['columns'][0]['observed'], ('1',))
        self.assertEqual(report['columns'][1]['observed'], ('2',))

    def test_sqlite_ref_lists_tables_and_scans_a_selected_table_lazily(self):
        pathname = os.path.join(self.tempdir.name, 'example.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute('create table customers (id integer, name text)')
            database.executemany(
                'insert into customers values (?, ?)',
                ((1, 'Ada'), (2, 'Grace'), (3, 'Linus')),
            )
            database.execute('create table audit (message text)')
            database.execute('insert into audit values (?)', ('created',))

        root = fetch(pathname)

        self.assertEqual(root['type'], 'database')
        self.assertNotIsInstance(root['tables'], (list, tuple))
        self.assertEqual(list_items(root), [
            {'name': 'audit', 'type': 'table'},
            {'name': 'customers', 'type': 'table'},
        ])
        self.assertEqual(
            [report['name'] for report in scan(root, limit=1)],
            ['audit', 'customers'],
        )

        table = fetch(pathname + '/customers')
        self.assertEqual(table['type'], 'table')
        self.assertEqual(list_items(table), [
            {'name': 'id', 'type': 'column'},
            {'name': 'name', 'type': 'column'},
        ])

        report = scan(fetch(pathname + '/customers'), limit=2)[0]
        self.assertEqual(report, {
            'name': 'customers',
            'row_count': 3,
            'rows_scanned': 2,
            'sampled': True,
            'columns': [
                {
                    'name': 'id',
                    'data_types': ('integer',),
                    'cardinality': 2,
                    'max_width': 1,
                    'observed': (1, 2),
                },
                {
                    'name': 'name',
                    'data_types': ('string',),
                    'cardinality': 2,
                    'max_width': 5,
                    'observed': ('Ada', 'Grace'),
                },
            ],
        })

    def test_sqlite_column_ref_is_a_leaf_and_scans_only_that_column(self):
        pathname = os.path.join(self.tempdir.name, 'columns.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute('create table customers (id integer, name text)')
            database.executemany(
                'insert into customers values (?, ?)',
                ((1, 'Ada'), (2, 'Grace'), (3, 'Linus')),
            )

        root = fetch(pathname + '/customers.name')

        self.assertEqual(root['type'], 'column')
        self.assertEqual(root['name'], 'customers.name')
        self.assertEqual(list_items(root), [])
        report = scan(root, limit=2)[0]
        self.assertEqual(report['row_count'], 3)
        self.assertEqual(report['rows_scanned'], 2)
        self.assertEqual(
            [column['name'] for column in report['columns']],
            ['name'],
        )
        self.assertEqual(report['columns'][0]['observed'], ('Ada', 'Grace'))

    def test_sqlite_fragment_is_not_a_table_selector(self):
        pathname = os.path.join(self.tempdir.name, 'no-fragment.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute('create table items (value integer)')

        self.assertFalse(SQLiteConnector().accepts(pathname + '#items'))

    def test_sqlite_encoded_dots_are_identifier_characters(self):
        pathname = os.path.join(self.tempdir.name, 'dotted.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute(
                'create table "events.archive" ("event.name" text)'
            )
            database.execute(
                'insert into "events.archive" values (?)', ('launch',)
            )

        root = fetch(pathname + '/events%2Earchive.event%2Ename')

        self.assertEqual(root['name'], 'events.archive.event.name')
        self.assertEqual(root['columns'], ('event.name',))
        self.assertEqual(
            scan(root)[0]['columns'][0]['observed'],
            ('launch',),
        )

    def test_sqlite_generated_columns_match_select_star_schema(self):
        pathname = os.path.join(self.tempdir.name, 'generated.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute(
                'create table measurements ('
                'value integer, '
                'doubled integer generated always as (value * 2) stored'
                ')'
            )
            database.execute('insert into measurements (value) values (3)')

        root = fetch(pathname + '/measurements')
        self.assertEqual(root['columns'], ('value', 'doubled'))

        output = self.run_cli('ls', '-l', pathname + '/measurements')
        self.assertIn('doubled', output)

        report = scan(root)[0]
        self.assertEqual(
            [column['observed'] for column in report['columns']],
            [(3,), (6,)],
        )

    def test_sqlite_schema_falls_back_when_table_xinfo_is_unavailable(self):
        database = MagicMock()
        database.execute.side_effect = (
            iter(()),
            iter(((0, 'value', 'INTEGER', 0, None, 0),)),
        )

        schema = SQLiteConnector._schema(database, '"items"')

        self.assertEqual(schema, ((0, 'value', 'INTEGER', 0, None, 0, 0),))
        self.assertEqual(database.execute.call_count, 2)

    def test_sqlite_scan_does_not_modify_wal_source_files(self):
        source = os.path.join(self.tempdir.name, 'source.sqlite')
        copy = os.path.join(self.tempdir.name, 'copy.sqlite')
        database = sqlite3.connect(source)
        self.addCleanup(database.close)
        database.execute('pragma journal_mode=wal')
        database.execute('pragma wal_autocheckpoint=0')
        database.execute('create table items (value integer)')
        database.execute('insert into items values (1)')
        database.commit()

        for suffix in ('', '-wal', '-shm'):
            shutil.copyfile(source + suffix, copy + suffix)
        wal_path = copy + '-wal'
        with open(wal_path, 'rb') as wal:
            wal_before = wal.read()

        report = scan(fetch(copy + '/items'))[0]

        self.assertEqual(report['row_count'], 1)
        self.assertTrue(os.path.exists(wal_path))
        with open(wal_path, 'rb') as wal:
            self.assertEqual(wal.read(), wal_before)

    def test_sqlite_schema_count_and_row_connections_close(self):
        pathname = os.path.join(self.tempdir.name, 'closed.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute('create table items (value integer)')
            database.execute('insert into items values (1)')
        connector = SQLiteConnector()
        connections = []

        def connect(_):
            connection = sqlite3.connect(pathname)
            connections.append(connection)
            return connection

        with patch.object(connector, '_connect', side_effect=connect):
            root = connector.fetch(pathname + '/items')
            self.assertEqual(list(root['rows']), [{'value': 1}])

        self.assertEqual(len(connections), 3)
        for connection in connections:
            with self.assertRaisesRegex(sqlite3.ProgrammingError, 'closed'):
                connection.execute('select 1')

    def test_scan_limit_does_not_pull_an_extra_lazy_row(self):
        def rows():
            yield ('1',)
            yield ('2',)
            raise AssertionError('scan pulled beyond its limit')

        report = scan({
            'type': 'table',
            'name': 'bounded',
            'columns': ('value',),
            'rows': rows(),
        }, limit=2)[0]

        self.assertEqual(report['rows_scanned'], 2)
        self.assertTrue(report['sampled'])
        self.assertIsNone(report['row_count'])

    def test_ls_command_lists_csv_columns_directly(self):
        pathname = self.write_csv(
            'customers.csv',
            'id,name\n1,Ada\n',
        )

        output = self.run_cli('ls', pathname)

        self.assertEqual(output, 'id\nname\n')

    def test_ls_all_includes_sqlite_system_tables(self):
        pathname = os.path.join(self.tempdir.name, 'system.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute(
                'create table items (id integer primary key autoincrement)'
            )
            database.execute('insert into items default values')

        ordinary = self.run_cli('ls', pathname)
        all_items = self.run_cli('ls', '-a', pathname)

        self.assertEqual(ordinary, 'items\n')
        self.assertEqual(all_items, 'items\nsqlite_sequence\n')

    def test_ls_verbose_describes_sqlite_tables(self):
        pathname = os.path.join(self.tempdir.name, 'verbose.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute(
                'create table customers (id integer, name text)'
            )
            database.executemany(
                'insert into customers values (?, ?)',
                ((1, 'Ada'), (2, 'Grace')),
            )

        output = self.run_cli('ls', '-l', pathname)

        self.assertIn('Table', output)
        self.assertIn('Columns', output)
        self.assertIn('Rows', output)
        self.assertIn('Size (MB)', output)
        self.assertRegex(output, r'customers\s+2\s+2\s+0')

    def test_ls_verbose_right_aligns_numeric_columns(self):
        root = {
            'type': 'database',
            'table_summaries': ({
                'name': 'customers',
                'type': 'table',
                'columns': 5,
                'rows': 23,
                'size': 2,
            },),
        }
        with patch(
                'gitdata.cli.gitdata_ls.fetch',
                return_value=root):
            output = self.run_cli('ls', '-l', 'example.sqlite')

        lines = output.splitlines()
        self.assertEqual(
            lines[0],
            '{} {} {} {}'.format(
                'Table'.ljust(35),
                'Columns'.rjust(10),
                'Rows'.rjust(15),
                'Size (MB)'.rjust(10),
            ),
        )
        self.assertEqual(
            lines[2],
            '{} {} {} {}'.format(
                'customers'.ljust(35),
                '5'.rjust(10),
                '23'.rjust(15),
                '2'.rjust(10),
            ),
        )

    def test_ls_verbose_describes_sqlite_columns_and_indexes(self):
        pathname = os.path.join(self.tempdir.name, 'schema.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute(
                'create table customers ('
                'id integer primary key, name text not null default "unknown")'
            )
            database.execute(
                'create unique index customers_name on customers (name)'
            )

        output = self.run_cli('ls', '-l', pathname + '/customers')

        self.assertIn('Column', output)
        self.assertRegex(output, r'id\s+INTEGER\s+YES\s+PRI')
        self.assertRegex(output, r'name\s+TEXT\s+NO\s+-\s+"unknown"')
        self.assertIn('Index', output)
        self.assertRegex(output, r'customers_name\s+YES\s+name')

    def test_ls_verbose_describes_sqlite_expression_indexes(self):
        pathname = os.path.join(self.tempdir.name, 'expression.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute('create table t (a text, b text)')
            database.execute('create index ix_pair on t (a, b)')
            database.execute('create index ix_expr on t (lower(a))')

        output = self.run_cli('ls', '-l', pathname + '/t')

        self.assertRegex(output, r'ix_pair\s+NO\s+a, b')
        self.assertRegex(output, r'ix_expr\s+NO\s+.*lower\(a\)')

    def test_ls_does_not_request_database_row_counts(self):
        root = {'type': 'column', 'name': 'items.value'}
        with patch(
                'gitdata.cli.gitdata_ls.fetch',
                return_value=root) as resolve:
            output = self.run_cli('ls', 'example.sqlite/items.value')

        self.assertEqual(output, '')
        resolve.assert_called_once_with(
            'example.sqlite/items.value', count_rows=False
        )

    def test_ls_verbose_does_not_eager_count_a_selected_table(self):
        root = {
            'type': 'table',
            'name': 'items',
            'columns': ('value',),
            'column_summaries': iter(({
                'name': 'value',
                'type': 'column',
                'data_type': 'INTEGER',
                'null': 'YES',
                'key': '-',
                'default': '-',
                'extra': '-',
            },)),
            'indexes': iter(()),
        }
        with patch(
                'gitdata.cli.gitdata_ls.fetch',
                return_value=root) as resolve:
            self.run_cli('ls', '-l', 'example.sqlite/items')

        resolve.assert_called_once_with(
            'example.sqlite/items', count_rows=False
        )

    def test_ls_verbose_on_a_column_is_empty(self):
        root = {'type': 'column', 'name': 'items.value'}
        with patch(
                'gitdata.cli.gitdata_ls.fetch',
                return_value=root):
            output = self.run_cli('ls', '-l', 'example.sqlite/items.value')

        self.assertEqual(output, '')

    def test_scan_announces_itself_after_fetching_data(self):
        error = StringIO()

        def fetch_before_announcement(*args, **kwargs):
            self.assertEqual(error.getvalue(), '')
            return {
                'type': 'table',
                'name': 'slow',
                'columns': (),
                'rows': iter(()),
            }

        with patch.object(sys, 'argv', ['gitdata', 'scan', 'slow.csv']):
            with patch(
                    'gitdata.cli.gitdata_scan.fetch',
                    side_effect=fetch_before_announcement):
                with redirect_stderr(error):
                    with redirect_stdout(StringIO()):
                        main()

        self.assertEqual(error.getvalue(), 'Scanning...\n')

    def test_scan_does_not_announce_an_invalid_ref(self):
        error = StringIO()
        with patch.object(sys, 'argv', ['gitdata', 'scan', 'not-a-ref']):
            with patch(
                    'gitdata.cli.gitdata_scan.fetch',
                    side_effect=ValueError('invalid ref')):
                with redirect_stderr(error):
                    with self.assertRaisesRegex(ValueError, 'invalid ref'):
                        main()

        self.assertEqual(error.getvalue(), '')

    def test_scan_title_uses_singular_column_and_row_labels(self):
        pathname = self.write_csv('one.csv', 'value\nonly\n')

        output = self.run_cli('scan', pathname)

        self.assertIn('one.csv: 1 column, 1 row\n', output)

    def test_scan_server_ref_requests_a_database_without_a_traceback(self):
        root = {
            'type': 'server',
            'name': 'localhost',
            'database_names': ('cocal',),
        }
        error = StringIO()
        with patch(
                'gitdata.cli.gitdata_scan.fetch',
                return_value=root):
            with patch('gitdata.cli.gitdata_scan.scan') as profile:
                with patch.object(
                        sys,
                        'argv',
                        ['gitdata', 'scan', 'mysql://localhost']):
                    with redirect_stderr(error):
                        with self.assertRaises(SystemExit) as raised:
                            main()

        self.assertEqual(error.getvalue(), '')
        self.assertEqual(
            str(raised.exception),
            'gitdata scan: please supply a database name, for example '
            'mysql://host/database; use gitdata ls on the server ref to list '
            'visible databases',
        )
        profile.assert_not_called()

    def test_sampled_scan_title_uses_singular_lower_bound(self):
        pathname = os.path.join(self.tempdir.name, 'sampled.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute('create table items (value integer)')
            database.executemany(
                'insert into items values (?)', ((1,), (2,))
            )

        output = self.run_cli(
            'scan', '--no-count', '--limit', '1', pathname + '/items'
        )

        self.assertIn('items: 1 column, at least 1 row (sampled)', output)

    def test_scan_command_profiles_csv_directly_and_marks_samples(self):
        pathname = self.write_csv(
            'customers.csv',
            'id,name\n1,Ada\n2,Grace\n3,Linus\n',
        )

        with patch(
                'shutil.get_terminal_size',
                return_value=os.terminal_size((100, 24))):
            output = self.run_cli('scan', '--limit', '2', pathname)

        self.assertIn('customers.csv: 2 columns, at least 2 rows (sampled)', output)
        self.assertNotIn('\t', output)
        self.assertTrue(all(line == line.rstrip() for line in output.splitlines()))
        self.assertIn(
            'Columns                        Data Types   Cardinality     Size '
            'Observed Values',
            output,
        )
        self.assertIn(
            '------------------------------ ------------ ----------- '
            '-------- ----------------------------------',
            output,
        )
        self.assertIn(
            'id                             string                ~2        1 '
            '1, 2',
            output,
        )
        self.assertIn(
            'name                           string                ~2        5 '
            'Ada, Grace',
            output,
        )

    def test_scan_no_count_skips_the_sqlite_eager_count(self):
        pathname = os.path.join(self.tempdir.name, 'no-count.sqlite')
        with sqlite3.connect(pathname) as database:
            database.execute('create table items (value integer)')
            database.executemany(
                'insert into items values (?)',
                ((1,), (2,), (3,)),
            )

        output = self.run_cli(
            'scan', '--no-count', '--limit', '2', pathname + '/items'
        )

        self.assertIn('items: 1 column, at least 2 rows (sampled)', output)


@unittest.skipUnless(
    os.environ.get('GITDATA_TEST_MYSQL_INSPECTION_HOST'),
    'MariaDB inspection service is not configured',
)
class MySQLDirectInspectionTests(unittest.TestCase):
    def setUp(self):
        password_name = 'GITDATA_TEST_MYSQL_INSPECTION_PASSWORD'
        self.password = os.environ[password_name]
        password_env = patch.dict(
            os.environ, {'GITDATA_PASSWORD_ENV': password_name}
        )
        password_env.start()
        self.addCleanup(password_env.stop)
        user = os.environ.get('GITDATA_TEST_MYSQL_INSPECTION_USER', 'root')
        host = os.environ['GITDATA_TEST_MYSQL_INSPECTION_HOST']
        port = os.environ.get('GITDATA_TEST_MYSQL_INSPECTION_PORT', '3306')
        self.database = os.environ.get(
            'GITDATA_TEST_MYSQL_INSPECTION_DATABASE',
            'gitdata_example',
        )
        self.server_ref = 'mysql://{}@{}:{}'.format(
            user,
            host,
            port,
        )
        self.ref = 'mysql://{}@{}:{}/{}'.format(
            user,
            host,
            port,
            self.database,
        )
        self.table_ref = 'mysql://{}@{}:{}/{}.customers'.format(
            user,
            host,
            port,
            self.database,
        )

    def test_mariadb_server_ref_lists_visible_databases(self):
        items = list_items(fetch(self.server_ref))

        self.assertIn(
            {'name': self.database, 'type': 'database'},
            items,
        )

    def test_mariadb_ref_lists_and_scans_dumped_example(self):
        root = fetch(self.ref)

        self.assertEqual(list_items(root), [
            {'name': 'customers', 'type': 'table'},
            {'name': 'orders', 'type': 'table'},
            {'name': 'products', 'type': 'table'},
        ])
        self.assertEqual(set(root), {
            'type', 'name', 'table_names', 'tables', 'table_summaries',
        })

        table = fetch(self.table_ref)
        self.assertEqual(table['columns'], (
            'customer_id',
            'name',
            'email',
            'country_code',
            'joined_on',
        ))

        report = scan(table, limit=2)[0]
        self.assertEqual(report['row_count'], 3)
        self.assertEqual(report['rows_scanned'], 2)
        self.assertTrue(report['sampled'])
        self.assertEqual(report['columns'][0]['observed'], (1, 2))
        self.assertEqual(
            report['columns'][1]['observed'],
            ('Ada Lovelace', 'Grace Hopper'),
        )


if __name__ == '__main__':
    unittest.main()
