"""Connectors that expose tabular refs as rooted Python structures."""

import csv
import os
from pathlib import Path
import sqlite3

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
