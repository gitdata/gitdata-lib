"""
    Test the gitdata database module
"""

# pylint: disable=too-many-public-methods
# pylint: disable=missing-docstring
# pylint: disable=invalid-name
# pylint: disable=no-member

# import configparser
# import os
import logging
import unittest
import os

from decimal import Decimal
from datetime import date

import gitdata
from gitdata.database import (
    connect,
    # connect_database,
    DatabaseException,
    # UnknownDatabaseException,
)

import warnings
warnings.filterwarnings('ignore', '\(1051, "Unknown table.*')

logger = logging.getLogger(__name__)

class DatabaseTests:
    """test db module"""

    # It's reasonable in this case.
    def tearDown(self):
        self.db('drop table if exists gitdata_test_table')
        self.db.close()
        print(self.db.report())

    def assertQueryResult(self, expected, cmd, *args, **kwargs):
        expected = '\n'.join(
            line for line in
            gitdata.utils.trim(expected).splitlines()
            if line
        )
        result = str(self.db(cmd, *args, **kwargs))
        print(expected)
        print(result)
        self.assertEqual(expected, result)

    def test_output(self):
        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

    def test_RecordSet(self):
        db = self.db
        db("""
            create table gitdata_test_table (
                ID CHAR(10),
                AMOUNT NUMERIC(10,2),
                DTADD DATE,NOTES TEXT
            )
        """)
        db("""
            insert into gitdata_test_table values (
                1234, 50,'2005-01-14', 'Hello there'
            )
        """)
        db("""
            insert into gitdata_test_table values (
                5678, 60,'2035-01-24', 'New notes'
            )
        """)
        recordset = db('select * from gitdata_test_table')
        for rec in recordset:
            self.assertEquals(rec, ("1234", 50, date(2005,1,14), "Hello there"))
            break

    def test_db_create_drop_table(self):
        db = self.db
        self.assert_('gitdata_test_table' not in db.get_table_names())
        db("""
            create table gitdata_test_table (
                ID CHAR(10),
                AMOUNT NUMERIC(10,2),
                DTADD DATE,
                NOTES TEXT
           )
        """)
        self.assert_('gitdata_test_table' in db.get_table_names())
        db('drop table gitdata_test_table')
        self.assert_('gitdata_test_table' not in db.get_table_names())

    def test_get_table_names(self):
        db = self.db
        n = 10
        for i in range(n):
            table_name = 'gitdata_test_table{}'.format(i)
            db('drop table if exists ' + table_name)
            self.assert_(table_name not in db.get_table_names())
            db("""
               create table {} (
                 ID CHAR(10),
                 AMOUNT NUMERIC(10,2),
                 DTADD DATE,
                 NOTES TEXT
               )
            """.format(table_name))
            self.assert_(table_name in db.get_table_names())

        for i in range(n):
            table_name = 'gitdata_test_table{}'.format(i)
            db('drop table ' + table_name)
            self.assert_(table_name not in db.get_table_names())

    def test_db_insert_update_record(self):
        # pylint: disable=protected-access
        insert_test = """
            insert into gitdata_test_table
            (id, name, dtadd, amount, notes)
            values (%s, %s, %s, %s, %s)
        """
        select_all = 'select count(*) from gitdata_test_table'

        db = self.db
        db('drop table if exists gitdata_test_table')
        db("""
            create table gitdata_test_table (
                id char(10),
                name char(25),
                amount numeric(10,2),
                dtadd date,
                notes text
            )
        """)
        dt = date(2005, 1, 2)
        db(insert_test, '1234', 'Joe', dt, 50, 'Testing')
        self.assertEqual(list(db(select_all))[0][0], 1)
        db(insert_test, '4321', 'Joe', dt, 10.20, 'Testing 2')
        self.assertEqual(list(db(select_all))[0][0], 2)
        db(insert_test, '4321', 'Joe', dt, None, 'Updated')
        self.assertEqual(list(db(select_all))[0][0], 3)

        response = db('select * from gitdata_test_table')
        print(response)
        self.assertEqual(
            list(db(
                'select * from gitdata_test_table'
            ))[2][4], "Updated")
        db('drop table gitdata_test_table')

    def test_last_rowid(self):
        db = self.db
        select_all = 'select count(*) from dz_test_contacts'
        db('drop table if exists dz_test_contacts')
        db(self.create_indexed_cmd)
        db("""insert into dz_test_contacts values
           (1,"testuser","pass","test@datagitdataer.net")""")
        self.assertEqual(db.lastrowid, 1)
        db("""insert into dz_test_contacts values
           (4,"2testuser","pass","test@datagitdataer.net")""")
        self.assertEqual(db.lastrowid, 4)
        db.execute_many(
            """insert into dz_test_contacts (userid, password, email) values
            (%s, %s, %s)""",
            [
                ('user3', 'pass3', 'user3@datagitdataer.net'),
                ('user4', 'pass4', 'user4@datagitdataer.net'),
                ('user5', 'pass5', 'user5@datagitdataer.net'),
                ('user6', 'pass6', 'user6@datagitdataer.net'),
            ])
        self.assertEqual(list(db(select_all))[0][0], 6)
        db('drop table dz_test_contacts')

    def test_record(self):
        db = self.db
        db("""create table gitdata_test_table (ID CHAR(10), AMOUNT
           NUMERIC(10,2), NOTES TEXT)""")
        db("""insert into gitdata_test_table values ("1234", 50, "Hello there")""")
        recordset = db('select * from gitdata_test_table')
        for rec in recordset:
            self.assertEqual(
                rec,
                ('1234', 50, "Hello there")
            )

    def test_metadata(self):
        db = self.db
        db("""create table gitdata_test_table (ID CHAR(10), AMOUNT
           NUMERIC(10,2), DTADD DATE, NOTES TEXT)""")
        db("""insert into gitdata_test_table values ("1234", 50, "2005-01-14",
           "Hello there")""")
        q = db('select * from gitdata_test_table')
        names = [f[0] for f in q.cursor.description]
        self.assertEqual(names, ['ID', 'AMOUNT', 'DTADD', 'NOTES'])

    def test_date_type(self):
        db = self.db
        db('create table gitdata_test_table (ID CHAR(10), AMOUNT NUMERIC(10,2), DTADD date, NOTES TEXT)')
        cmd = 'insert into gitdata_test_table values ("1234", 50, %s, "Hello there")'
        db(cmd, date(2005, 1, 14))
        recordset = db('select * from gitdata_test_table')
        for rec in recordset:
            self.assertEqual(
                rec,
                ('1234', 50, date(2005, 1, 14), "Hello there")
            )

    def test_decimal_type(self):
        db = self.db
        db(self.create_cmd)
        cmd = 'insert into gitdata_test_table values (%s, %s, %s, %s)'
        db(cmd, '1234', 50, Decimal('1.12'), 'Hello there')
        recordset = db('select * from gitdata_test_table')
        for rec in recordset:
            self.assertEqual(
                rec,
                ('1234', 50, Decimal('1.12'), "Hello there")
            )

    def test_standardized_paramstyle(self):

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table where amount > %s', 20
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
            """,
            'select * from test_table where amount < %(amount)s', dict(amount=20)
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
            """,
            'select * from test_table where notes like "%%1"'
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             2   30.2     75 notes 2
            """,
            'select * from test_table where notes like "%%2" and amount > %s', 20
        )

    def test_execute_many_from_empty_list_of_tuples(self):

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.db.execute_many(
            'insert into test_table values (%s, %s, %s, %s)', [
            ]
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

    def test_execute_many_from_list_of_tuples(self):

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.db.execute_many(
            'insert into test_table values (%s, %s, %s, %s)', [
                (4, 50.10, '20.00', 'notes 4'),
                (5, 60.10, '20.00', 'notes 5'),
            ]
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
             4   50.1     20 notes 4
             5   60.1     20 notes 5
            """,
            'select * from test_table'
        )

    def test_execute_many_from_list_of_one_tuple(self):

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.db.execute_many(
            'insert into test_table values (%s, %s, %s, %s)', [
                (4, 50.10, '20.00', 'notes 4'),
            ]
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
             4   50.1     20 notes 4
            """,
            'select * from test_table'
        )

    def test_execute_many_from_empty_list_of_dicts(self):

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.db.execute_many(
            'insert into test_table values (%(id)s, %(amount)s, %(salary)s, %(notes)s)', [
            ]
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

    def test_execute_many_from_list_of_dicts(self):

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.db.execute_many(
            'insert into test_table values (%(id)s, %(amount)s, %(salary)s, %(notes)s)', [
                dict(id=4, amount=50.10, salary='20.00', notes='notes 4'),
                dict(id=5, amount=60.10, salary='20.00', notes='notes 5'),
            ]
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
             4   50.1     20 notes 4
             5   60.1     20 notes 5
            """,
            'select * from test_table'
        )

    def test_execute_many_from_list_of_one_dict(self):

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.db.execute_many(
            'insert into test_table values (%(id)s, %(amount)s, %(salary)s, %(notes)s)', [
                dict(id=4, amount=50.10, salary='20.00', notes='notes 4'),
            ]
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
             4   50.1     20 notes 4
            """,
            'select * from test_table'
        )

    # def test_column_name_reserved(self):
    #     db = self.db
    #     self.assertNotIn('z_test_table', db.get_table_names())
    #     db("""
    #        create table z_test_table (
    #          `id` integer,
    #          `column` text(20),
    #          `created` timestamp
    #        )
    #     """)
    #     self.assertIn('z_test_table', db.get_table_names())
    #     db('drop table z_test_table')
    #     self.assertNotIn('z_test_table', db.get_table_names())


class TestSqlite3Database(unittest.TestCase, DatabaseTests):

    def setUp(self):
        self.db = connect()
        self.create_cmd  = """
            create table gitdata_test_table
            (
                ID CHAR(10),
                AMOUNT NUMERIC(10,2),
                salary decimal(10,2),
                NOTES TEXT
            )
        """
        self.create_indexed_cmd = """
            create table dz_test_contacts (
                contactid integer PRIMARY KEY AUTOINCREMENT,
                userid char(20),
                password char(16),
                email char(60)
            )
        """
        self.db("""
            create table test_table
            (
                id char(10),
                amount numeric(10,2),
                salary decimal(10,0),
                notes text
            )
        """)
        self.db.execute_many(
            'insert into test_table values (%s, %s, %s, %s)', [
                [1, 10.20, '50.00', 'notes 1'],
                [2, 30.20, '75.00', 'notes 2'],
                [3, 40.10, '20.00', 'notes 3'],
            ]
        )
        self.db.debug = True

    # def test_create_site_tables(self):
    #     self.db.create_site_tables()
    #     assert 'users' in self.db.get_table_names()

    # def test_create_and_delete_test_tables(self):
    #     self.db.create_test_tables()
    #     try:
    #         assert 'account' in self.db.get_table_names()
    #     finally:
    #         self.db.create_test_tables()
    #     self.db.delete_test_tables()
    #     assert 'account' not in self.db.get_table_names()

    def test_native_paramstyle(self):
        self.db.paramstyle = 'native'

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table'
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             2   30.2     75 notes 2
             3   40.1     20 notes 3
            """,
            'select * from test_table where amount > ?', 20
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
            """,
            'select * from test_table where amount < :amount', dict(amount=20)
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             1   10.2     50 notes 1
            """,
            'select * from test_table where notes like "%1"'
        )

        self.assertQueryResult(
            """
            id amount salary notes
            -- ------ ------ -------
             2   30.2     75 notes 2
            """,
            'select * from test_table where notes like "%2" and amount > ?', 20
        )

    def test_exception(self):
        db = self.db
        self.assertRaises(DatabaseException, db, 'select things')

    def test_exception_with_binary(self):
        db = self.db
        db('create table blobs (id integer, data blob)')
        db('insert into blobs values (1, %s)', 'blob1')
        self.assertRaises(
            DatabaseException,
            db,
            'insert into blobs values whoops (1, %s)',
            b'blob1'
        )
        try:
            db('insert into blobs values whoops (1, %s)', b'blob1')
        except DatabaseException as e:
            self.assertEqual(str(e),
            """
  statement: 'insert into blobs values whoops (1, ?)'
  parameters: ['[5 bytes]']
  message: near "whoops": syntax error
""")

    def test_exception_long_parameter(self):
        db = self.db
        db('create table blobs (id integer, data blob)')
        self.assertRaises(
            DatabaseException,
            db,
            'insert into blobs values whoops (1, %s)',
            '*' * 101
        )
        try:
            db(
                'insert into blobs values whoops (1, %s)',
                '*' * 101
            )
        except DatabaseException as e:
            self.assertEqual(str(e),
            """
  statement: 'insert into blobs values whoops (1, ?)'
  parameters: ['**************************************************[1 chars]**************************************************']
  message: near "whoops": syntax error
""")

class TestPostgreSQLDatabase(unittest.TestCase, DatabaseTests):

    def setUp(self):
        get = os.environ.get

        def create_database(name):
            if name in self.db.database_names:
                self.db(f'drop database {name}')
            self.db(f'create database {name}')

        self.db = db = connect(
            'postgresql',
            host=get('GITDATA_TEST_DATABASE_HOST', 'localhost'),
            user=get('GITDATA_TEST_DATABASE_USER', 'postgres'),
            password=get('GITDATA_TEST_DATABASE_PASSWORD', 'password'),
        )

        db.connect()
        db.get_connection().autocommit = True
        db('drop database if exists gitdatatest')
        create_database('gitdatatest')
        create_database('gitdatatest2')

        cmd = """
        create table test_table2 (
            name varchar(20),
            size int
        ); commit;
        """
        db2 = self.db.use('gitdatatest2')
        db2(cmd)

        self.create_cmd = """
            create table test_table
            (
                id char(10),
                amount numeric(10,1),
                salary decimal(10,0),
                notes text
            )
        """
        self.create_indexed_cmd = """
            create table dz_test_contacts (
                contactid integer PRIMARY KEY AUTO_INCREMENT,
                userid char(20),
                password char(16),
                email char(60)
            )
        """
        self.db('drop table if exists test_table')
        self.db(self.create_cmd)

        self.db('drop table if exists gitdata_test_table')
        self.db('drop table if exists test_table')
        self.db("""
            create table test_table
            (
                id char(10),
                amount numeric(10,1),
                salary decimal(10,0),
                notes text
            )
        """)
        self.db.execute_many(
            'insert into test_table values (%s, %s, %s, %s)', [
                [1, 10.20, '50.00', 'notes 1'],
                [2, 30.20, '75.00', 'notes 2'],
                [3, 40.10, '20.00', 'notes 3'],
            ]
        )

        self.create_cmd2 = """
            create table test_table
            (
                id char(10),
                amount numeric(10,1),
                salary decimal(10,0),
                notes text
            )
        """

    def tearDown(self):
        self.db('drop database gitdatatest2')
        self.db('drop database gitdatatest')
        self.db.close()
        print(self.db.report())

    @unittest.skip
    def test_RecordSet(self):
        pass

    @unittest.skip
    def test_date_type(self):
        pass

    @unittest.skip
    def test_decimal_type(self):
        pass

    @unittest.skip
    def test_last_rowid(self):
        pass

    @unittest.skip
    def test_metadata(self):
        pass

    @unittest.skip
    def test_record(self):
        pass

    @unittest.skip
    def test_standardized_paramstyle(self):
        pass

    def otest_something(self):
        print(self.db('select * from test_table'))
        self.test_execute_many_from_empty_list_of_tuples()

    def test_table_names(self):
        db1 = self.db
        self.assertIn(
            'test_table',
            self.db.table_names,
        )

    def test_use(self):
        db1 = self.db
        db2 = self.db.use('gitdatatest2')
        self.assertNotIn(
            'test_table2',
            self.db.table_names,
        )
        self.assertIn(
            'test_table2',
            db2.table_names,
        )

    def test_connect(self):
        self.assertIn(
            'postgres',
            self.db.get_database_names(),
        )

    def test_get_table_names(self):
        self.assertIn(
            'test_table',
            self.db.get_table_names(),
        )


class TestMySQLDatabase(unittest.TestCase, DatabaseTests):

    def setUp(self):
        get = os.environ.get

        self.db = connect(
            'mysql',
            host=get('GITDATA_TEST_DATABASE_HOST', 'localhost'),
            user=get('GITDATA_TEST_DATABASE_USER', 'testuser'),
            passwd=get('GITDATA_TEST_DATABASE_PASSWORD', 'password'),
            db='gitdatatest'
        )
        self.create_cmd  = """
            create table gitdata_test_table
            (
                ID CHAR(10),
                AMOUNT NUMERIC(10,1),
                salary decimal(10,2),
                NOTES TEXT
            )
        """
        self.create_indexed_cmd = """
            create table dz_test_contacts (
                contactid integer PRIMARY KEY AUTO_INCREMENT,
                userid char(20),
                password char(16),
                email char(60)
            )
        """
        self.db('drop table if exists gitdata_test_table')
        self.db('drop table if exists test_table')
        self.db("""
            create table test_table
            (
                id char(10),
                amount numeric(10,1),
                salary decimal(10,0),
                notes text
            )
        """)
        self.db.execute_many(
            'insert into test_table values (%s, %s, %s, %s)', [
                [1, 10.20, '50.00', 'notes 1'],
                [2, 30.20, '75.00', 'notes 2'],
                [3, 40.10, '20.00', 'notes 3'],
            ]
        )
        self.db.debug = True

    def test_get_column_names(self):
        db = self.db
        db('create table gitdata_test_table (ID CHAR(10), AMOUNT NUMERIC(10,2), DTADD date, NOTES TEXT)')
        cmd = 'insert into gitdata_test_table values ("1234", 50, %s, "Hello there")'
        db(cmd, date(2005, 1, 14))
        column_names = db.get_column_names('gitdata_test_table')
        self.assertEqual(
            column_names,
            ('id', 'amount', 'dtadd', 'notes')
        )

    def test_paramstyle(self):
        self.db.paramstyle = 'qmark'
        new = self.db.translate('select * from test_table where amount=%(n)s', dict(n=50))
        self.assertEqual(new, ('select * from test_table where amount=:n', {'n': 50}))

#     def test_connect_database(self):
#         get = os.environ.get
#         config = configparser.ConfigParser()
#         config['database'] = dict(
#             host=get('GITDATA_TEST_DATABASE_HOST', 'localhost'),
#             user=get('GITDATA_TEST_DATABASE_USER', 'testuser'),
#             password=get('GITDATA_TEST_DATABASE_PASSWORD', 'password'),
#             name='gitdatatest',
#             engine='mysql'
#         )
#         db = connect_database(config)
#         db("""create table gitdata_test_table (ID CHAR(10), AMOUNT
#            NUMERIC(10,2), NOTES TEXT)""")
#         db("""insert into gitdata_test_table values ("1234", 50, "Hello there")""")
#         recordset = db('select * from gitdata_test_table')
#         for rec in recordset:
#             self.assertEqual(
#                 rec,
#                 ('1234', 50, "Hello there")
#             )
#         db('drop table gitdata_test_table')

#     def test_connect_database_legacy(self):
#         get = os.environ.get
#         config = configparser.ConfigParser()
#         config['database'] = dict(
#             dbhost=get('GITDATA_TEST_DATABASE_HOST', 'localhost'),
#             dbuser=get('GITDATA_TEST_DATABASE_USER', 'testuser'),
#             dbpass=get('GITDATA_TEST_DATABASE_PASSWORD', 'password'),
#             dbname='gitdatatest',
#             engine='mysql'
#         )
#         db = connect_database(config)
#         db("""create table gitdata_test_table (ID CHAR(10), AMOUNT
#            NUMERIC(10,2), NOTES TEXT)""")
#         db("""insert into gitdata_test_table values ("1234", 50, "Hello there")""")
#         recordset = db('select * from gitdata_test_table')
#         for rec in recordset:
#             self.assertEqual(
#                 rec,
#                 ('1234', 50, "Hello there")
#             )
#         db('drop table gitdata_test_table')

#     def test_connect_unknown(self):
#         self.assertRaises(UnknownDatabaseException, database, 'nodb')

#     def test_use(self):
#         def get_parameters():
#             get = os.environ.get
#             config = configparser.ConfigParser()
#             config['database'] = dict(
#                 host=get('GITDATA_TEST_DATABASE_HOST', 'localhost'),
#                 user=get('GITDATA_TEST_DATABASE_USER', 'testuser'),
#                 password=get('GITDATA_TEST_DATABASE_PASSWORD', 'password'),
#                 name='gitdatatest',
#                 engine='mysql'
#             )
#             return config

#         def create_data(db, tablename):
#             db('drop table if exists %s' % tablename)
#             db("""create table %s (ID CHAR(10), AMOUNT
#                NUMERIC(10,2), NOTES TEXT)""" % tablename)

#         config = get_parameters()

#         db1 = connect_database(config)
#         create_data(db1, 'z_test_table1')

#         # in Travis this is already done
#         db1('create database if not exists gitdatatest2')

#         db2 = db1.use('gitdatatest2')
#         try:
#             create_data(db2, 'z_test_table2')

#             assert 'z_test_table1' in db1.get_table_names()
#             assert 'z_test_table2' not in db1.get_table_names()

#             assert 'z_test_table1' not in db2.get_table_names()
#             assert 'z_test_table2' in db2.get_table_names()

#             db1('drop table z_test_table1')
#             db2('drop table z_test_table2')

#         finally:
#             # in Travis this isn't needed but won't cause problems either
#             db1('drop database if exists gitdatatest2')

#     def test_get_database_names(self):
#         db = self.db

#         databases = db.get_database_names()
#         assert 'gitdatatest' in databases

#         # in Travis this is already done
#         db('create database if not exists gitdatatest2')
#         try:

#             assert 'gitdatatest2' in db.get_database_names()

#         finally:
#             # in Travis this isn't needed but won't cause problems either
#             db('drop database if exists gitdatatest2')
#             assert 'gitdatatest2' not in db.get_database_names()

#     def test_create_and_delete_test_tables(self):
#         # in Travis this is already done
#         self.db('create database if not exists gitdatatest2')

#         db = self.db.use('gitdatatest2')
#         try:

#             assert 'gitdatatest2' in db.get_database_names()
#             db.create_test_tables()
#             try:
#                 assert 'account' in db.get_table_names()
#             finally:
#                 db.delete_test_tables()

#             assert 'account' not in db.get_table_names()

#         finally:
#             # in Travis this isn't needed but won't cause problems either
#             db('drop database if exists gitdatatest2')
#             assert 'gitdatatest2' not in db.get_database_names()

#         stats = db.get_stats()
#         assert isinstance(stats, list)

#     def test_run(self):
#         root = os.path.dirname(__file__)
#         join = os.path.join
#         self.db.run(join(root, 'sql/mysql_run_test_start.sql'))
#         assert 'run_test_table' in self.db.get_table_names()
#         self.db.run(join(root, 'sql/mysql_run_test_finish.sql'))
#         assert 'run_test_table' not in self.db.get_table_names()

#     def test_runs(self):
#         root = os.path.dirname(__file__)
#         join = os.path.join

#         start = gitdata.load(join(root, 'sql/mysql_run_test_start.sql'))
#         self.db.runs(start)
#         assert 'run_test_table' in self.db.get_table_names()

#         finish = gitdata.load(join(root, 'sql/mysql_run_test_finish.sql'))
#         self.db.runs(finish)
#         assert 'run_test_table' not in self.db.get_table_names()

#     def test_runs_with_blank_lines(self):
#         root = os.path.dirname(__file__)
#         join = os.path.join
#         self.db.run(join(root, 'sql/mysql_run_test_start.sql'))

#         cmd = """
#         select * from run_test_table where name=%s;
#         """
#         self.db.runs(cmd, 'pat jones')

#         finish = gitdata.load(join(root, 'sql/mysql_run_test_finish.sql'))
#         self.db.runs(finish)
#         assert 'run_test_table' not in self.db.get_table_names()

#     def test_native_paramstyle(self):
#         self.db.paramstyle = 'native'

#         self.assertQueryResult(
#             """
#             id amount salary notes
#             -- ------ ------ -------
#              1   10.2     50 notes 1
#              2   30.2     75 notes 2
#              3   40.1     20 notes 3
#             """,
#             'select * from test_table'
#         )

#         self.assertQueryResult(
#             """
#             id amount salary notes
#             -- ------ ------ -------
#              2   30.2     75 notes 2
#              3   40.1     20 notes 3
#             """,
#             'select * from test_table where amount > %s', 20
#         )

#         self.assertQueryResult(
#             """
#             id amount salary notes
#             -- ------ ------ -------
#              1   10.2     50 notes 1
#             """,
#             'select * from test_table where amount < %(amount)s', dict(amount=20)
#         )

#         self.assertQueryResult(
#             """
#             id amount salary notes
#             -- ------ ------ -------
#              1   10.2     50 notes 1
#             """,
#             'select * from test_table where notes like "%%1"'
#         )

#         self.assertQueryResult(
#             """
#             id amount salary notes
#             -- ------ ------ -------
#              2   30.2     75 notes 2
#             """,
#             'select * from test_table where notes like "%%2" and amount > %s', 20
#         )

#     def test_make_select_statement(self):
#         from gitdata.sqltools import make_table_select, less_than, gt
#         cmd = make_table_select('test_table', amount=less_than(20))
#         self.assertQueryResult(
#             """
#             id amount salary notes
#             -- ------ ------ -------
#              1   10.2     50 notes 1
#             """,
#             *cmd
#         )

#         cmd = make_table_select('test_table', amount=gt(20))
#         self.assertQueryResult(
#             """
#             id amount salary notes
#             -- ------ ------ -------
#              2   30.2     75 notes 2
#              3   40.1     20 notes 3
#             """,
#             *cmd
#         )


# class TestTranslate(unittest.TestCase):

#     def setUp(self):
#         self.db = database('sqlite3', ':memory:')

#     def assertTranslateResult(self, expected, cmd, *args, **kwargs):
#         result = self.db.translate(cmd, *args, **kwargs)
#         print(expected)
#         print(result)
#         self.assertEqual(expected, result)

#     def test_translate_to_named_paramstyle(self):
#         self.db.paramstyle = 'named'

#         self.assertTranslateResult(
#             ('select * from test_table where amount=:1', (50,)),
#             'select * from test_table where amount=%s', 50
#         )

#         self.assertTranslateResult(
#             ('select * from test_table where amount=:amount', {'amount': 50}),
#             'select * from test_table where amount=%(amount)s', dict(amount=50)
#         )

#         self.assertTranslateResult(
#             ('select * from test_table where notes like "%1" and amount > :1', (50,)),
#             'select * from test_table where notes like "%%1" and amount > %s', 50
#         )

#     def test_translate_to_qmark_paramstyle(self):
#         self.db.paramstyle = 'qmark'

#         self.assertTranslateResult(
#             ('select * from test_table where amount=?', (50,)),
#             'select * from test_table where amount=%s', 50
#         )

#         self.assertTranslateResult(
#             ('select * from test_table where amount=:amount', {'amount': 50}),
#             'select * from test_table where amount=%(amount)s', dict(amount=50)
#         )

#         self.assertTranslateResult(
#             ('select * from test_table where notes like "%1" and amount > ?', (50,)),
#             'select * from test_table where notes like "%%1" and amount > %s', 50
#         )


