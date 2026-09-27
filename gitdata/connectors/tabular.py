"""Connectors that expose tabular refs as rooted Python structures."""

import csv
import getpass
import os
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, unquote, urlsplit

import pymysql

from gitdata.connectors.common import BaseConnector


class CsvConnector(BaseConnector):
    """Resolve a local CSV file into one table root."""

    def accepts(self, ref):
        return (
            isinstance(ref, str)
            and os.path.isfile(ref)
            and ref.lower().endswith('.csv')
        )

    def fetch(self, ref):
        if not self.accepts(ref):
            return None

        with open(ref, 'r', encoding='utf-8-sig', newline='') as source:
            columns = tuple(next(csv.reader(source), ()))

        def rows():
            with open(ref, 'r', encoding='utf-8-sig', newline='') as source:
                reader = csv.reader(source)
                next(reader, None)
                for row_number, row in enumerate(reader, start=2):
                    if len(row) != len(columns):
                        raise ValueError(
                            'CSV row {} has {} values; expected {}'.format(
                                row_number, len(row), len(columns)
                            )
                        )
                    yield tuple(row)

        return {
            'type': 'table',
            'name': os.path.basename(ref),
            'columns': columns,
            'rows': rows(),
        }


class MariaDBConnector(BaseConnector):
    """Resolve a MariaDB/MySQL URL into a database or table root."""

    schemes = ('mariadb', 'mysql')
    row_cursor_class = pymysql.cursors.SSCursor

    @staticmethod
    def _quoted(name):
        return '`{}`'.format(name.replace('`', '``'))

    def accepts(self, ref):
        return (
            isinstance(ref, str)
            and urlsplit(ref).scheme.lower() in self.schemes
        )

    def _parts(self, ref):
        parts = urlsplit(ref)
        query = parse_qs(parts.query, keep_blank_values=True)
        unexpected = set(query) - {'password_env'}
        if unexpected:
            raise ValueError(
                'Unsupported MariaDB ref option(s): {}'.format(
                    ', '.join(sorted(unexpected))
                )
            )

        database = unquote(parts.path.lstrip('/'))
        if not parts.hostname or '/' in database:
            raise ValueError(
                'MariaDB refs require a host and at most one database name'
            )
        if not database and parts.fragment:
            raise ValueError(
                'MariaDB table refs require a database name'
            )

        if parts.password is not None:
            raise ValueError(
                'Inline MariaDB passwords are not supported; use password_env'
            )
        if query.get('password_env'):
            variable = query['password_env'][-1]
            try:
                password = os.environ[variable]
            except KeyError:
                raise ValueError(
                    'MariaDB password environment variable {!r} is not set'
                    .format(variable)
                )
        else:
            password = None

        config = {
            'host': parts.hostname,
            'port': parts.port or 3306,
            'user': (
                unquote(parts.username)
                if parts.username is not None
                else getpass.getuser()
            ),
            'password': password,
            'charset': 'utf8mb4',
            'autocommit': True,
        }
        if database:
            config['database'] = database
        table = unquote(parts.fragment) if parts.fragment else None
        return config, table

    @staticmethod
    def _connect(config):
        database = pymysql.connect(**config)
        try:
            with database.cursor() as cursor:
                cursor.execute('set session transaction read only')
        except Exception:
            database.close()
            raise
        return database

    def _table(self, config, name):
        database = self._connect(config)
        try:
            with database.cursor() as cursor:
                cursor.execute(
                    'select column_name from information_schema.columns '
                    'where table_schema=%s and table_name=%s '
                    'order by ordinal_position',
                    (config['database'], name),
                )
                columns = tuple(row[0] for row in cursor)
        finally:
            database.close()

        if not columns:
            raise ValueError('Table {!r} not found'.format(name))

        quoted = self._quoted(name)

        def rows():
            connection = self._connect(config)
            cursor = connection.cursor(self.row_cursor_class)
            try:
                cursor.execute('select * from {}'.format(quoted))
                for row in cursor:
                    yield row
            finally:
                # SSCursor.close() drains unread rows. Detach the unbuffered
                # result before closing its socket so a bounded scan neither
                # fetches the remainder nor triggers destructor-time reads.
                result = getattr(cursor, '_result', None)
                setattr(cursor, 'connection', None)
                if result is not None:
                    result.unbuffered_active = False
                    result.connection = None
                setattr(connection, '_result', None)
                connection.close()

        return {
            'type': 'table',
            'name': name,
            'columns': columns,
            'rows': rows(),
        }

    def fetch(self, ref):
        if not self.accepts(ref):
            return None
        config, selected_table = self._parts(ref)
        if 'database' not in config:
            connection = self._connect(config)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('show databases')
                    names = tuple(row[0] for row in cursor)
            finally:
                connection.close()
            return {
                'type': 'server',
                'name': config['host'],
                'database_names': names,
            }
        if selected_table:
            return self._table(config, selected_table)

        database = self._connect(config)
        try:
            with database.cursor() as cursor:
                cursor.execute(
                    'select table_name from information_schema.tables '
                    "where table_schema=%s and table_type='BASE TABLE' "
                    'order by table_name',
                    (config['database'],),
                )
                names = tuple(row[0] for row in cursor)
        finally:
            database.close()

        def tables():
            for name in names:
                yield self._table(config, name)

        return {
            'type': 'database',
            'name': config['database'],
            'table_names': names,
            'tables': tables(),
        }


class SQLiteConnector(BaseConnector):
    """Resolve a local SQLite database or selected table."""

    suffixes = ('.db', '.sqlite', '.sqlite3')

    def _parts(self, ref):
        pathname, separator, table = ref.partition('#')
        return pathname, table if separator else None

    def accepts(self, ref):
        if not isinstance(ref, str):
            return False
        pathname, _ = self._parts(ref)
        if not os.path.isfile(pathname):
            return False
        if pathname.lower().endswith(self.suffixes):
            return True
        with open(pathname, 'rb') as source:
            return source.read(16) == b'SQLite format 3\x00'

    @staticmethod
    def _quoted(name):
        return '"{}"'.format(name.replace('"', '""'))

    @staticmethod
    def _connect(pathname):
        uri = Path(pathname).resolve().as_uri() + '?mode=ro'
        return sqlite3.connect(uri, uri=True)

    def _table(self, pathname, name):
        quoted = self._quoted(name)
        with self._connect(pathname) as database:
            try:
                schema = database.execute(
                    'pragma table_xinfo({})'.format(quoted)
                )
                columns = tuple(
                    row[1] for row in schema if row[6] != 1
                )
            except sqlite3.OperationalError:
                columns = tuple(
                    row[1] for row in database.execute(
                        'pragma table_info({})'.format(quoted)
                    )
                )
            if not columns:
                raise ValueError('Table {!r} not found'.format(name))

        def rows():
            with self._connect(pathname) as database:
                database.row_factory = sqlite3.Row
                for row in database.execute('select * from {}'.format(quoted)):
                    yield dict(row)

        return {
            'type': 'table',
            'name': name,
            'columns': columns,
            'rows': rows(),
        }

    def fetch(self, ref):
        if not self.accepts(ref):
            return None
        pathname, selected_table = self._parts(ref)
        if selected_table:
            return self._table(pathname, selected_table)

        with self._connect(pathname) as database:
            names = tuple(
                row[0] for row in database.execute(
                    "select name from sqlite_master "
                    "where type='table' and name not like 'sqlite_%' "
                    "order by name"
                )
            )

        def tables():
            for name in names:
                yield self._table(pathname, name)

        return {
            'type': 'database',
            'name': os.path.basename(pathname),
            'table_names': names,
            'tables': tables(),
        }
