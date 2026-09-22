"""Integration tests for Oracle Database support.

These tests run only when the GITDATA_TEST_ORACLE_* environment variables are
set. They are exercised locally against Oracle Free and can be enabled in CI
when an Oracle service is available.
"""

import os
import unittest

from gitdata.database import DatabaseException, connect


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

    def setUp(self):
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
        self.assertIn('gitdata_test', self.db.get_schema_names())
        self.assertIn('freepdb1', self.db.get_database_names())

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
