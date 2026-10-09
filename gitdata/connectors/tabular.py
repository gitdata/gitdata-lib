"""Connectors that expose tabular refs as rooted Python structures."""

import csv
from contextlib import closing
import getpass
import os
from pathlib import Path
import sqlite3
from urllib.parse import unquote, urlsplit

import pymysql

from gitdata.connectors.common import (
    BaseConnector,
    ConnectorError,
    password_from_environment,
)


class CsvConnector(BaseConnector):
    """Resolve a local CSV file into one table root."""

    def accepts(self, ref):
        return (
            isinstance(ref, str)
            and os.path.isfile(ref)
            and ref.lower().endswith('.csv')
        )

    def fetch(self, ref, count_rows=True):
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
            'format': 'csv',
            'name': os.path.basename(ref),
            'columns': columns,
            'rows': rows(),
        }


class MariaDBConnector(BaseConnector):
    """Resolve a MariaDB/MySQL URL into a database or table root."""

    schemes = ('mariadb', 'mysql')
    row_cursor_class = pymysql.cursors.SSCursor
    system_databases = (
        'information_schema',
        'mysql',
        'performance_schema',
        'sys',
    )

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
        if '?' in ref:
            raise ValueError('MariaDB refs do not accept query parameters')
        if '#' in ref:
            raise ValueError(
                'MariaDB refs do not accept fragment selectors; use '
                'database.table'
            )

        raw_database = parts.path.lstrip('/')
        if '/' in raw_database:
            raise ValueError(
                'MariaDB refs accept only one database and table selection'
            )
        dotted_table = None
        if '.' in raw_database:
            if raw_database.count('.') != 1:
                raise ValueError(
                    'MariaDB refs accept one database.table selection'
                )
            raw_database, raw_table = raw_database.split('.', 1)
            if not raw_database or not raw_table:
                raise ValueError(
                    'MariaDB dotted refs require both database and table names'
                )
            database = unquote(raw_database)
            dotted_table = unquote(raw_table)
        else:
            database = unquote(raw_database)
        table = dotted_table

        if not parts.hostname or '/' in database or (table and '/' in table):
            raise ValueError(
                'MariaDB refs require a host and at most one database name'
            )
        if not database and table:
            raise ValueError(
                'MariaDB table refs require a database name'
            )

        if parts.password is not None:
            raise ValueError(
                'Inline MariaDB passwords are not supported; set PASSWORD or '
                'name another variable with GITDATA_PASSWORD_ENV'
            )
        password = password_from_environment('MariaDB')

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
        return config, table

    @staticmethod
    def _connect(config):
        try:
            database = pymysql.connect(**config)
        except pymysql.OperationalError as error:
            code = error.args[0] if error.args else None
            host = config['host'].encode('unicode_escape').decode('ascii')
            address = '{}:{}'.format(host, config['port'])
            if code == 2003:
                message = (
                    'could not connect to MySQL server at {}. '
                    'Check the server name, confirm MySQL is running, and '
                    'verify network access.'.format(address)
                )
            elif code == 1045:
                message = (
                    'could not authenticate MySQL user {!r} at {}. '
                    'Check the user name and password.'.format(
                        config['user'], address
                    )
                )
            elif code == 1049:
                message = (
                    'MySQL database {!r} was not found at {}. '
                    'Check the database name.'.format(
                        config['database'], address
                    )
                )
            else:
                code = code if isinstance(code, int) else 'unknown'
                message = (
                    'MySQL could not open a connection to {} (error {}). '
                    'Check the server settings and access permissions.'.format(
                        address, code
                    )
                )
            raise ConnectorError(message) from None
        try:
            with database.cursor() as cursor:
                cursor.execute('set session transaction read only')
        except BaseException:
            database.close()
            raise
        return database

    def _table(self, config, name, count_rows):
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

        def eager_count():
            connection = self._connect(config)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('select count(*) from {}'.format(quoted))
                    return cursor.fetchone()[0]
            finally:
                connection.close()

        row_count = eager_count() if count_rows else None

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

        def column_summaries():
            connection = self._connect(config)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('describe {}'.format(quoted))
                    for row in cursor:
                        yield {
                            'name': row[0],
                            'type': 'column',
                            'data_type': row[1],
                            'null': row[2],
                            'key': row[3] or '-',
                            'default': row[4] if row[4] is not None else '-',
                            'extra': row[5] or '-',
                        }
            finally:
                connection.close()

        def indexes():
            connection = self._connect(config)
            try:
                by_name = {}
                order = []
                with connection.cursor() as cursor:
                    cursor.execute('show index from {}'.format(quoted))
                    for row in cursor:
                        index_name = row[2]
                        if index_name not in by_name:
                            by_name[index_name] = {
                                'name': index_name,
                                'unique': 'YES' if row[1] == 0 else 'NO',
                                'columns': [],
                            }
                            order.append(index_name)
                        column = row[4]
                        if column is None:
                            column = row[14] if len(row) > 14 else None
                            column = column or '<expression>'
                        by_name[index_name]['columns'].append(column)
                for index_name in order:
                    item = by_name[index_name]
                    item['columns'] = ', '.join(item['columns'])
                    yield item
            finally:
                connection.close()

        return {
            'type': 'table',
            'name': name,
            'columns': columns,
            'row_count': row_count,
            'rows': rows(),
            'column_summaries': column_summaries(),
            'indexes': indexes(),
        }

    def fetch(self, ref, count_rows=True):
        if not self.accepts(ref):
            return None
        config, selected_table = self._parts(ref)
        if 'database' not in config:
            connection = self._connect(config)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('show databases')
                    all_names = tuple(row[0] for row in cursor)
            finally:
                connection.close()
            names = tuple(
                name for name in all_names
                if name.lower() not in self.system_databases
            )

            def database_summaries(include_system=False):
                stats_connection = self._connect(config)
                try:
                    with stats_connection.cursor() as cursor:
                        query = (
                            'select s.schema_name, count(t.table_name), '
                            'coalesce(sum(t.table_rows), 0), '
                            'round(coalesce(sum('
                            't.data_length + t.index_length), 0) / 1024 / 1024) '
                            'from information_schema.schemata s '
                            'left join information_schema.tables t '
                            'on t.table_schema = s.schema_name '
                            "and t.table_type='BASE TABLE' "
                        )
                        if include_system:
                            cursor.execute(
                                query +
                                'group by s.schema_name order by s.schema_name'
                            )
                        else:
                            cursor.execute(
                                query +
                                'where s.schema_name not in (%s, %s, %s, %s) '
                                'group by s.schema_name order by s.schema_name',
                                self.system_databases,
                            )
                        for row in cursor:
                            yield {
                                'name': row[0],
                                'type': 'database',
                                'tables': int(row[1]),
                                'rows': int(row[2]),
                                'size': int(row[3]),
                            }
                finally:
                    stats_connection.close()

            return {
                'type': 'server',
                'name': config['host'],
                'database_names': names,
                'all_database_names': all_names,
                'database_summaries': database_summaries(),
                'all_database_summaries': database_summaries(True),
            }
        if selected_table:
            return self._table(config, selected_table, count_rows)

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
                yield self._table(config, name, count_rows)

        def table_summaries():
            stats_connection = self._connect(config)
            try:
                with stats_connection.cursor() as cursor:
                    cursor.execute(
                        'select t.table_name, count(c.column_name), '
                        'coalesce(t.table_rows, 0), '
                        'round(coalesce('
                        't.data_length + t.index_length, 0) / 1024 / 1024) '
                        'from information_schema.tables t '
                        'left join information_schema.columns c '
                        'on c.table_schema = t.table_schema '
                        'and c.table_name = t.table_name '
                        'where t.table_schema=%s '
                        "and t.table_type='BASE TABLE' "
                        'group by t.table_name, t.table_rows, '
                        't.data_length, t.index_length '
                        'order by t.table_name',
                        (config['database'],),
                    )
                    for row in cursor:
                        yield {
                            'name': row[0],
                            'type': 'table',
                            'columns': int(row[1]),
                            'rows': int(row[2]),
                            'size': int(row[3]),
                        }
            finally:
                stats_connection.close()

        return {
            'type': 'database',
            'name': config['database'],
            'table_names': names,
            'tables': tables(),
            'table_summaries': table_summaries(),
        }


class SQLiteConnector(BaseConnector):
    """Resolve a local SQLite database or selected table."""

    suffixes = ('.db', '.sqlite', '.sqlite3')

    def _is_sqlite_path(self, pathname):
        if not os.path.isfile(pathname):
            return False
        if pathname.lower().endswith(self.suffixes):
            return True
        with open(pathname, 'rb') as source:
            return source.read(16) == b'SQLite format 3\x00'

    def _parts(self, ref):
        if self._is_sqlite_path(ref):
            return ref, None, None
        pathname, separator, selector = ref.rpartition('/')
        if not separator or not selector or not self._is_sqlite_path(pathname):
            return ref, None, None
        if selector.count('.') > 1:
            raise ValueError(
                'SQLite refs accept one table.column selection'
            )
        raw_table, dot, raw_column = selector.partition('.')
        if not raw_table or (dot and not raw_column):
            raise ValueError(
                'SQLite refs require a table before an optional column'
            )
        return (
            pathname,
            unquote(raw_table),
            unquote(raw_column) if dot else None,
        )

    def accepts(self, ref):
        if not isinstance(ref, str):
            return False
        pathname, table, _ = self._parts(ref)
        return self._is_sqlite_path(pathname) and (
            table is not None or pathname == ref
        )

    @staticmethod
    def _quoted(name):
        return '"{}"'.format(name.replace('"', '""'))

    @staticmethod
    def _connect(pathname):
        uri = Path(pathname).resolve().as_uri() + '?mode=ro'
        return sqlite3.connect(uri, uri=True)

    @staticmethod
    def _schema(database, quoted):
        try:
            schema = tuple(database.execute(
                'pragma table_xinfo({})'.format(quoted)
            ))
            if schema:
                return schema
        except sqlite3.OperationalError:
            pass
        return tuple(
            tuple(row) + (0,)
            for row in database.execute(
                'pragma table_info({})'.format(quoted)
            )
        )

    def _table(
            self, pathname, name, selected_column=None, count_rows=True):
        quoted = self._quoted(name)
        with closing(self._connect(pathname)) as database:
            all_columns = tuple(
                row[1] for row in self._schema(database, quoted)
                if row[6] != 1
            )
            if not all_columns:
                raise ValueError('Table {!r} not found'.format(name))
            if selected_column is not None and selected_column not in all_columns:
                raise ValueError(
                    'Column {!r} not found in table {!r}'.format(
                        selected_column, name
                    )
                )

        if selected_column is None:
            columns = all_columns
            projection = '*'
            root_type = 'table'
            root_name = name
        else:
            columns = (selected_column,)
            projection = self._quoted(selected_column)
            root_type = 'column'
            root_name = '{}.{}'.format(name, selected_column)

        def eager_count():
            with closing(self._connect(pathname)) as database:
                return database.execute(
                    'select count(*) from {}'.format(quoted)
                ).fetchone()[0]

        row_count = eager_count() if count_rows else None

        def rows():
            with closing(self._connect(pathname)) as database:
                database.row_factory = sqlite3.Row
                for row in database.execute(
                        'select {} from {}'.format(projection, quoted)):
                    yield dict(row)

        def column_summaries():
            with closing(self._connect(pathname)) as database:
                for row in self._schema(database, quoted):
                    if row[6] == 1:
                        continue
                    if selected_column is not None and row[1] != selected_column:
                        continue
                    yield {
                        'name': row[1],
                        'type': 'column',
                        'data_type': row[2] or '-',
                        'null': 'NO' if row[3] else 'YES',
                        'key': 'PRI' if row[5] else '-',
                        'default': row[4] if row[4] is not None else '-',
                        'extra': '-',
                    }

        def indexes():
            if selected_column is not None:
                return
            with closing(self._connect(pathname)) as database:
                for row in database.execute(
                        'pragma index_list({})'.format(quoted)):
                    index_name = row[1]
                    columns = [
                        info[2]
                        for info in database.execute(
                            'pragma index_info({})'.format(
                                self._quoted(index_name)
                            )
                        )
                    ]
                    if any(column is None for column in columns):
                        index_sql = database.execute(
                            "select sql from sqlite_master "
                            "where type='index' and name=?",
                            (index_name,),
                        ).fetchone()[0]
                        columns = [index_sql]
                    yield {
                        'name': index_name,
                        'unique': 'YES' if row[2] else 'NO',
                        'columns': ', '.join(columns),
                    }

        return {
            'type': root_type,
            'name': root_name,
            'columns': columns,
            'row_count': row_count,
            'rows': rows(),
            'column_summaries': column_summaries(),
            'indexes': indexes(),
        }

    def fetch(self, ref, count_rows=True):
        if not self.accepts(ref):
            return None
        pathname, selected_table, selected_column = self._parts(ref)
        if selected_table:
            return self._table(
                pathname, selected_table, selected_column, count_rows
            )

        with closing(self._connect(pathname)) as database:
            all_names = tuple(
                row[0] for row in database.execute(
                    "select name from sqlite_master "
                    "where type='table' order by name"
                )
            )
        names = tuple(
            name for name in all_names
            if not name.lower().startswith('sqlite_')
        )

        def selected_tables(selected_names):
            for name in selected_names:
                yield self._table(
                    pathname, name, count_rows=count_rows
                )

        def table_summaries(selected_names):
            with closing(self._connect(pathname)) as database:
                for name in selected_names:
                    quoted = self._quoted(name)
                    columns = sum(
                        1 for row in self._schema(database, quoted)
                        if row[6] != 1
                    )
                    rows = database.execute(
                        'select count(*) from {}'.format(quoted)
                    ).fetchone()[0]
                    sample = list(database.execute(
                        'select * from {} limit 100'.format(quoted)
                    ))
                    payload = sum(
                        sum(
                            0 if value is None else
                            len(value) if isinstance(value, (bytes, bytearray)) else
                            len(value.encode('utf-8')) if isinstance(value, str) else
                            8
                            for value in row
                        )
                        for row in sample
                    )
                    size = round(
                        (payload / len(sample) if sample else 0)
                        * rows / 1024 / 1024
                    )
                    yield {
                        'name': name,
                        'type': 'table',
                        'columns': columns,
                        'rows': rows,
                        'size': size,
                    }

        return {
            'type': 'database',
            'name': os.path.basename(pathname),
            'table_names': names,
            'all_table_names': all_names,
            'tables': selected_tables(names),
            'all_tables': selected_tables(all_names),
            'table_summaries': table_summaries(names),
            'all_table_summaries': table_summaries(all_names),
        }
