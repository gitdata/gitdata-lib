"""
    gitdata postgresql database
"""

import logging
import psycopg2

from ..utils import obfuscate
from .common import Database

logger = logging.getLogger(__name__)


class PostgreSQLDatabase(Database):
    """PostgresSQL Database"""

    paramstyle = 'pyformat'
    connect_string_schema = 'postgresql'

    def __init__(self, *args, **kwargs):
        """Initialize with standard postgresql parameters"""
        Database.__init__(self, psycopg2.connect, *args, **kwargs)

    def get_database_names(self):
        """Return Databases"""
        cmd = """
        SELECT datname FROM pg_database
        WHERE datistemplate = false
        """
        return [r[0] for r in self(cmd)]

    def get_schema_names(self):
        """Return schema names"""
        cmd = """
        SELECT schema_name
        FROM information_schema.tables
        ORDER BY schema_name
        """
        return [r[0] for r in self(cmd)]

    def get_table_names(self):
        """Return Table names"""
        cmd = """
        SELECT table_name
        FROM information_schema.tables
        ORDER BY table_name
        """
        return [r[0] for r in self(cmd)]

    def connect_to_database(self, name):
        self.db(f'\\c {name}')

    def use(self, name):
        """use another database on the same instance"""
        return self._use(dbname=name)

    def get_column_names(self, table_name):
        cmd = """
        SELECT column_name
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = %s;
        """
        return [t for t, in self(cmd, table_name)]

    @property
    def connect_string(self):
        """Return a string representation of the connection parameters"""
        get = self.__kwargs.get
        user = get('user', '')
        password = get('password')
        return '{}://{}{}{}{}'.format(
            self.connect_string_schema,
            user,
            password and ':' + obfuscate(str(password)) or '',
            ('@' if user or password else '') + get('host', 'localhost'),
            '/' + get('database', '') if get('database') else ''
        )

    def __str__(self):
        return '<{} {!r}>'.format(
            self.__class__.__name__,
            self.connect_string
        )
