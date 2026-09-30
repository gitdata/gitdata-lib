"""Integration tests for Oracle Database support.

These tests run only when the GITDATA_TEST_ORACLE_* environment variables are
set. They are exercised locally against Oracle Free and can be enabled in CI
when an Oracle service is available.
"""

import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch
from urllib.parse import quote

from gitdata.cli import main
from gitdata.connectors import fetch
from gitdata.database import DatabaseException, connect
from gitdata.inspection import list_items, scan


_ORACLE_ENV = (
    'GITDATA_TEST_ORACLE_USER',
    'GITDATA_TEST_ORACLE_PASSWORD',
    'GITDATA_TEST_ORACLE_SERVICE_NAME',
)


@unittest.skipUnless(
    all(os.environ.get(name) for name in _ORACLE_ENV),
    'Oracle integration environment is not configured',
)
class TestOracleDatabase(unittest.TestCase):

    table_name = 'gitdata_oracle_test'
    quoted_table_name = 'GitDataOracleMixed'

    def _run_cli(self, *arguments):
        output = StringIO()
        error = StringIO()
        with patch.object(sys, 'argv', ['gitdata'] + list(arguments)):
            with redirect_stdout(output), redirect_stderr(error):
                main()
        return output.getvalue(), error.getvalue()

    def setUp(self):
        password_env = patch.dict(
            os.environ,
            {'GITDATA_PASSWORD_ENV': 'GITDATA_TEST_ORACLE_PASSWORD'},
        )
        password_env.start()
        self.addCleanup(password_env.stop)
        get = os.environ.get
        self.db = connect(
            'oracle',
            host=get('GITDATA_TEST_ORACLE_HOST', '127.0.0.1'),
            port=int(get('GITDATA_TEST_ORACLE_PORT', '1521')),
            service_name=get('GITDATA_TEST_ORACLE_SERVICE_NAME'),
            user=get('GITDATA_TEST_ORACLE_USER'),
            password=get('GITDATA_TEST_ORACLE_PASSWORD'),
        )
        self._drop_table()
        self._drop_quoted_table()

    def _ref(self, table=None):
        get = os.environ.get
        ref = 'oracle://{}@{}:{}/{}'.format(
            quote(os.environ['GITDATA_TEST_ORACLE_USER'], safe=''),
            get('GITDATA_TEST_ORACLE_HOST', '127.0.0.1'),
            int(get('GITDATA_TEST_ORACLE_PORT', '1521')),
            quote(os.environ['GITDATA_TEST_ORACLE_SERVICE_NAME'], safe=''),
        )
        if table is not None:
            ref += '/' + quote(table, safe='')
        return ref

    def tearDown(self):
        self._drop_table()
        self._drop_quoted_table()
        self.db.close()

    def _drop_table(self):
        try:
            self.db('DROP TABLE {}'.format(self.table_name))
        except DatabaseException as error:
            if 'ORA-00942' not in str(error):
                raise

    def _drop_quoted_table(self):
        try:
            self.db('DROP TABLE "{}"'.format(self.quoted_table_name))
        except DatabaseException as error:
            if 'ORA-00942' not in str(error):
                raise

    def _create_table(self):
        self.db("""
            CREATE TABLE {} (
                id NUMBER(10) PRIMARY KEY,
                display_name VARCHAR2(100),
                amount NUMBER(10, 2)
            )
        """.format(self.table_name))

    def test_query_parameters_and_metadata(self):
        self._create_table()
        self.db.execute_many(
            'INSERT INTO {} VALUES (%s, %s, %s)'.format(self.table_name),
            [(1, 'one', 10.25), (2, 'two', 20.50)],
        )
        self.db.execute_many(
            'INSERT INTO {} VALUES (%(id)s, %(name)s, %(amount)s)'.format(
                self.table_name
            ),
            [{'id': 3, 'name': 'three', 'amount': 30.75}],
        )
        self.db.commit()

        rows = list(self.db(
            'SELECT id, display_name FROM {} WHERE id > %s ORDER BY id'.format(
                self.table_name
            ),
            1,
        ))

        self.assertEqual(rows, [(2, 'two'), (3, 'three')])
        self.assertIn(self.table_name, self.db.get_table_names())
        self.assertEqual(
            self.db.get_column_names(self.table_name),
            ('id', 'display_name', 'amount'),
        )
        self.assertIn(
            os.environ['GITDATA_TEST_ORACLE_USER'].lower(),
            self.db.get_schema_names(),
        )
        self.assertIn(
            os.environ['GITDATA_TEST_ORACLE_SERVICE_NAME'].lower(),
            self.db.get_database_names(),
        )

    def test_direct_connector_lists_and_scans_oracle_tables(self):
        self._create_table()
        self.db.execute_many(
            'INSERT INTO {} VALUES (%s, %s, %s)'.format(self.table_name),
            [(1, 'one', 10.25), (2, 'two', 20.50), (3, 'three', 30.75)],
        )
        self.db.commit()

        output, error = self._run_cli('ls', self._ref())
        self.assertIn(self.table_name, output.splitlines())
        self.assertEqual(error, '')

        output, error = self._run_cli(
            'scan', '--limit', '2', self._ref(self.table_name)
        )
        self.assertIn(
            '{}: 3 columns, 3 rows (sampled)'.format(self.table_name),
            output,
        )
        self.assertEqual(error, 'Scanning...\n')

        database = fetch(self._ref(), count_rows=False)
        self.assertIn(self.table_name, database['table_names'])
        summary = next(
            item for item in list_items(database, verbose=True)
            if item['name'] == self.table_name
        )
        self.assertEqual(summary['columns'], 3)

        table = fetch(self._ref(self.table_name), count_rows=True)
        self.assertEqual(table['columns'], ('id', 'display_name', 'amount'))
        column_summary = list_items(table, verbose=True)
        self.assertEqual(column_summary[0]['key'], 'PRI')
        self.assertEqual(
            [column['data_type'] for column in column_summary],
            ['NUMBER(10)', 'VARCHAR2(100)', 'NUMBER(10,2)'],
        )
        report = scan(table, limit=2)[0]
        self.assertEqual(report['row_count'], 3)
        self.assertEqual(report['rows_scanned'], 2)
        self.assertTrue(report['sampled'])

    def test_quoted_metadata_names_round_trip_to_column_lookup(self):
        self.db('''
            CREATE TABLE "{}" (
                "MixedColumn" NUMBER(10),
                "lowercase_column" VARCHAR2(100),
                ORDINARY_COLUMN NUMBER(10)
            )
        '''.format(self.quoted_table_name))

        table_name = next(
            name for name in self.db.get_table_names()
            if name == self.quoted_table_name
        )
        self.assertEqual(
            self.db.get_column_names(table_name),
            ('MixedColumn', 'lowercase_column', 'ordinary_column'),
        )
        direct_table = fetch(
            self._ref('"{}"'.format(self.quoted_table_name)),
            count_rows=False,
        )
        self.assertEqual(direct_table['name'], '"GitDataOracleMixed"')
        self.assertEqual(
            direct_table['columns'],
            ('"MixedColumn"', '"lowercase_column"', 'ordinary_column'),
        )

    def test_rollback(self):
        self._create_table()
        self.db(
            'INSERT INTO {} VALUES (%s, %s, %s)'.format(self.table_name),
            1,
            'rolled back',
            99.99,
        )
        self.db.rollback()

        count = list(self.db(
            'SELECT COUNT(*) FROM {}'.format(self.table_name)
        ))[0][0]
        self.assertEqual(count, 0)
