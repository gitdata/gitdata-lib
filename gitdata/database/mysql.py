"""
    gitdata mysql database
"""

import logging
import pymysql

from ..utils import obfuscate
from .common import Database

logger = logging.getLogger(__name__)


class MySQLDatabaseTransaction:

    save_autocommit = None

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.save_autocommit = self.db.autocommit_mode
        self.db.autocommit(0)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type is not None:
            self.db.rollback()
            result = False
        else:
            self.db.commit()
            result = True
        self.db.autocommit(self.save_autocommit)
        return result


class MySQLDatabase(Database):
    """MySQL Database"""

    paramstyle = 'pyformat'
    connect_string_schema = 'mysql'

    def __init__(self, *args, **kwargs):
        """Initialize with standard pymysql parameters"""

        keyword_args = dict(
            kwargs,
            charset='utf8',
            binary_prefix=True
        )

        Database.__init__(self, pymysql.connect, *args, **keyword_args)

    def get_table_names(self):
        """return table names"""
        cmd = 'show tables'
        return [a[0] for a in self(cmd)]

    def get_database_names(self):
        """return database names"""
        cmd = 'show databases'
        return [a[0] for a in self(cmd)]

    def get_column_names(self, table):
        """return column names for a table"""
        rows = self('describe %s' % table)
        return tuple(rec[0].lower() for rec in rows)

    @property
    def connect_string(self):
        """Return a string representation of the connection parameters"""

        return '{}://{}{}@{}/{}'.format(
            self.connect_string_schema,
            self.user.decode('utf8'),
            self.password and ':' + obfuscate(str(self.password)) or '',
            str(self.host),
            self.db.decode('utf8'),
        )

    def __str__(self):
        return '<{} {!r}>'.format(
            self.__class__.__name__,
            self.connect_string,
        )

    def transaction(self):
        return MySQLDatabaseTransaction(self)

    def __del__(self):
        try:
            if self.open:
                self.close()
                logger.debug('closed %s', self.__class__.__name__)
        except (pymysql.OperationalError, NameError):
            pass
