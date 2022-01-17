"""
    test sql
"""

import unittest

import gitdata.database
from gitdata.sql import get_sql


class TestSQL(unittest.TestCase):

    def setUp(self):
        self.db = db = gitdata.database.connect()
        db('create table users (username char(10))')
        db('insert into users values (%s)', 'guest')

    def test_table(self):
        sql = get_sql(db=self.db)
        self.assertIn(
            'guest', [u['username'] for u in sql.users]
        )

    def test_query(self):
        sql = get_sql(db=self.db)
        self.assertIn(
            'guest', [u['username'] for u in sql.select_users]
        )

    def test_query_iter(self):
        sql = get_sql(db=self.db)
        for user in sql.select_users:
            self.assertEqual(
                user, dict(username='guest')
            )
