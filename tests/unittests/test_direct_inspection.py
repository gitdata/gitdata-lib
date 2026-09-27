"""Direct inspection of rooted Connector output."""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, patch

import pymysql

from gitdata.cli import main
from gitdata.connectors import fetch
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

    def write_csv(self, name, text):
        pathname = os.path.join(self.tempdir.name, name)
        with open(pathname, 'w', encoding='utf-8', newline='') as output:
            output.write(text)
        return pathname

    def run_cli(self, *arguments):
        output = StringIO()
        with patch.object(sys, 'argv', ['gitdata'] + list(arguments)):
            with redirect_stdout(output):
                main()
        return output.getvalue()

    def test_tabular_connectors_participate_in_connector_discovery(self):
        connector_types = set(get_connectors())

        self.assertTrue(issubclass(CsvConnector, BaseConnector))
        self.assertTrue(issubclass(MariaDBConnector, BaseConnector))
        self.assertTrue(issubclass(SQLiteConnector, BaseConnector))
        self.assertIn(CsvConnector, connector_types)
        self.assertIn(MariaDBConnector, connector_types)
        self.assertIn(SQLiteConnector, connector_types)

    def test_mariadb_rows_use_an_unbuffered_cursor(self):
        self.assertIs(
            MariaDBConnector.row_cursor_class,
            pymysql.cursors.SSCursor,
        )

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

    def test_mariadb_inline_passwords_are_rejected_without_echoing_them(self):
        ref = 'mysql://root:not-for-logs@127.0.0.1/gitdata_example'

        with self.assertRaisesRegex(ValueError, 'password_env') as raised:
            MariaDBConnector()._parts(ref)

        self.assertNotIn('not-for-logs', str(raised.exception))

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

        table = fetch(pathname + '#customers')
        self.assertEqual(table['type'], 'table')
        self.assertEqual(list_items(table), [
            {'name': 'id', 'type': 'column'},
            {'name': 'name', 'type': 'column'},
        ])

        report = scan(fetch(pathname + '#customers'), limit=2)[0]
        self.assertEqual(report, {
            'name': 'customers',
            'row_count': None,
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

        root = fetch(pathname + '#measurements')
        self.assertEqual(root['columns'], ('value', 'doubled'))

        report = scan(root)[0]
        self.assertEqual(
            [column['observed'] for column in report['columns']],
            [(3,), (6,)],
        )

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

        report = scan(fetch(copy + '#items'))[0]

        self.assertEqual(report['row_count'], 1)
        self.assertTrue(os.path.exists(wal_path))
        with open(wal_path, 'rb') as wal:
            self.assertEqual(wal.read(), wal_before)

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

    def test_scan_command_profiles_csv_directly_and_marks_samples(self):
        pathname = self.write_csv(
            'customers.csv',
            'id,name\n1,Ada\n2,Grace\n3,Linus\n',
        )

        output = self.run_cli('scan', '--limit', '2', pathname)

        self.assertIn('customers.csv: 2 columns, at least 2 rows (sampled)', output)
        self.assertIn('Column\tData Types\tCardinality\tSize\tObserved Values', output)
        self.assertIn('id\tstring\t~2\t1\t1, 2', output)
        self.assertIn('name\tstring\t~2\t5\tAda, Grace', output)


@unittest.skipUnless(
    os.environ.get('GITDATA_TEST_MYSQL_INSPECTION_HOST'),
    'MariaDB inspection service is not configured',
)
class MySQLDirectInspectionTests(unittest.TestCase):
    def setUp(self):
        password_name = 'GITDATA_TEST_MYSQL_INSPECTION_PASSWORD'
        self.password = os.environ[password_name]
        self.ref = 'mysql://{}@{}:{}/{}?password_env={}'.format(
            os.environ.get('GITDATA_TEST_MYSQL_INSPECTION_USER', 'root'),
            os.environ['GITDATA_TEST_MYSQL_INSPECTION_HOST'],
            os.environ.get('GITDATA_TEST_MYSQL_INSPECTION_PORT', '3306'),
            os.environ.get(
                'GITDATA_TEST_MYSQL_INSPECTION_DATABASE',
                'gitdata_example',
            ),
            password_name,
        )

    def test_mariadb_ref_lists_and_scans_dumped_example(self):
        root = fetch(self.ref)

        self.assertEqual(list_items(root), [
            {'name': 'customers', 'type': 'table'},
            {'name': 'orders', 'type': 'table'},
            {'name': 'products', 'type': 'table'},
        ])
        self.assertEqual(set(root), {
            'type', 'name', 'table_names', 'tables',
        })

        table = fetch(self.ref + '#customers')
        self.assertEqual(table['columns'], (
            'customer_id',
            'name',
            'email',
            'country_code',
            'joined_on',
        ))

        report = scan(table, limit=2)[0]
        self.assertEqual(report['rows_scanned'], 2)
        self.assertTrue(report['sampled'])
        self.assertEqual(report['columns'][0]['observed'], (1, 2))
        self.assertEqual(
            report['columns'][1]['observed'],
            ('Ada Lovelace', 'Grace Hopper'),
        )


if __name__ == '__main__':
    unittest.main()
