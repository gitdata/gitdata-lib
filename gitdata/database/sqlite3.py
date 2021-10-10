"""
    gitdata sqlite3 database
"""

from decimal import Decimal
import sqlite3
import logging

import gitdata
from gitdata.database import Database

logger = logging.getLogger(__name__)


class Sqlite3DatabaseTransaction:

    save_isolation_level = None

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.save_isolation_level = self.db.isolation_level
        self.db.isolation_level = 'DEFERRED'
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type is not None:
            self.db.rollback()
            result = False
        else:
            self.db.commit()
            result = True
        self.db.isolation_level = self.save_isolation_level
        return result


class Sqlite3Database(Database):
    """Sqlite3 Database"""

    paramstyle = 'qmark'
    connect_string_schema = 'sqlite3'

    def __init__(self, *args, **kwargs):
        """Initialize with standard sqlite3 parameters"""

        self._database = kwargs.setdefault('database', ':memory:')

        keyword_args = dict(
            kwargs,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )

        # add support for decimal types
        def adapt_decimal(value):
            """adapt decimal values to their string representation"""
            return str(value)

        def convert_decimal(bytetext):
            """convert bytesring representatinos of decimal values to actual
            Decimal values"""
            return Decimal(bytetext.decode())

        kwargs.setdefault('isolation_level', None)  # autocommit
        sqlite3.register_adapter(Decimal, adapt_decimal)
        sqlite3.register_converter('decimal', convert_decimal)

        Database.__init__(self, sqlite3.connect, *args, **keyword_args)

    def get_table_names(self):
        """return table names"""
        cmd = 'select name from sqlite_master where type="table"'
        return [a[0] for a in self(cmd)]

    @property
    def connect_string(self):
        """Return a string representation of the connection parameters"""

        return '{}:///{}'.format(
            self.connect_string_schema,
            str(self._database),
        )

    def transaction(self):
        return Sqlite3DatabaseTransaction(self)

def setup_test():
    """Setup Test Database"""
    db = Sqlite3Database()
    db.run(gitdata.utils.libpath('database/sqlite3_setup_test_data.sql'))
    return db
