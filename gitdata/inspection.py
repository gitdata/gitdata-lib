"""Read-only consumers of rooted Connector output."""

from datetime import date, datetime
from decimal import Decimal
import os
import re
import sqlite3
import tempfile


TYPE_NAMES = {
    type(None): 'null',
    bool: 'boolean',
    int: 'integer',
    float: 'double',
    Decimal: 'decimal',
    str: 'string',
    bytes: 'bytes',
    date: 'date',
    datetime: 'datetime',
}


INTEGER_TEXT = re.compile(r'^[+-]?(?:0|[1-9][0-9]*)$')
DECIMAL_TEXT = re.compile(
    r'^[+-]?(?:'
    r'(?:0|[1-9][0-9]*)\.[0-9]*'
    r'|\.[0-9]+'
    r'|(?:0|[1-9][0-9]*)[eE][+-]?[0-9]+'
    r'|(?:0|[1-9][0-9]*)\.[0-9]*[eE][+-]?[0-9]+'
    r'|\.[0-9]+[eE][+-]?[0-9]+'
    r')$'
)


def _csv_value_type(value):
    lowered = value.lower()
    if lowered in ('true', 'false'):
        return 'boolean'
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        pass
    else:
        if parsed.isoformat() == value:
            return 'date'
    if 'T' in value or ' ' in value:
        try:
            datetime.fromisoformat(value)
        except ValueError:
            pass
        else:
            return 'datetime'
    if INTEGER_TEXT.match(value):
        return 'integer'
    return 'decimal' if DECIMAL_TEXT.match(value) else 'string'


def _csv_data_type(types):
    if not types:
        return '-'
    if types <= {'integer', 'decimal'}:
        return 'decimal' if 'decimal' in types else 'integer'
    if types <= {'date', 'datetime'}:
        return 'datetime' if 'datetime' in types else 'date'
    if len(types) == 1:
        return next(iter(types))
    return 'mixed'


def _csv_column_summaries(table):
    profiles = [
        {
            'types': set(),
            'empty': 0,
            'width': 0,
            'example': None,
        }
        for _ in table['columns']
    ]
    row_count = 0
    rows = iter(table['rows'])
    with tempfile.TemporaryDirectory(prefix='gitdata-csv-profile-') as directory:
        pathname = os.path.join(directory, 'distinct.sqlite')
        database = sqlite3.connect(pathname)
        try:
            database.execute('PRAGMA journal_mode=OFF')
            database.execute('PRAGMA synchronous=OFF')
            database.execute(
                'CREATE TABLE distinct_values ('
                'column_index INTEGER NOT NULL, '
                'value TEXT NOT NULL, '
                'PRIMARY KEY (column_index, value)'
                ') WITHOUT ROWID'
            )
            for row in rows:
                row_count += 1
                for index, value in enumerate(row):
                    text = value.strip()
                    profile = profiles[index]
                    profile['width'] = max(profile['width'], len(value))
                    if not text:
                        profile['empty'] += 1
                        continue
                    profile['types'].add(_csv_value_type(text))
                    database.execute(
                        'INSERT OR IGNORE INTO distinct_values '
                        '(column_index, value) VALUES (?, ?)',
                        (index, value),
                    )
                    if profile['example'] is None:
                        profile['example'] = value
            distinct_counts = dict(database.execute(
                'SELECT column_index, COUNT(*) FROM distinct_values '
                'GROUP BY column_index'
            ))
        finally:
            database.close()
            close = getattr(rows, 'close', None)
            if close is not None:
                close()

    return [
        {
            'name': name,
            'type': 'column',
            'data_type': _csv_data_type(profile['types']),
            'empty': profile['empty'],
            'distinct': distinct_counts.get(index, 0),
            'candidate_key': (
                'YES'
                if row_count and not profile['empty']
                and distinct_counts.get(index, 0) == row_count
                else 'NO'
            ),
            'width': profile['width'],
            'example': profile['example'] or '-',
        }
        for index, (name, profile) in enumerate(zip(table['columns'], profiles))
    ]


def list_items(root, verbose=False, show_all=False):
    """Describe the immediate children of a supported root."""
    if root.get('type') == 'server':
        if verbose and show_all and 'all_database_summaries' in root:
            return list(root['all_database_summaries'])
        if verbose and 'database_summaries' in root:
            return list(root['database_summaries'])
        names = (
            root.get('all_database_names', root['database_names'])
            if show_all else root['database_names']
        )
        return [
            {'name': name, 'type': 'database'}
            for name in names
        ]
    if root.get('type') == 'column':
        return []
    if root.get('type') == 'table':
        if verbose and root.get('format') == 'csv':
            return _csv_column_summaries(root)
        if verbose and 'column_summaries' in root:
            return list(root['column_summaries'])
        return [
            {'name': name, 'type': 'column'}
            for name in root['columns']
        ]
    if root.get('type') == 'database':
        if verbose and show_all and 'all_table_summaries' in root:
            return list(root['all_table_summaries'])
        if verbose and 'table_summaries' in root:
            return list(root['table_summaries'])
        if verbose:
            tables = (
                root.get('all_tables', root['tables'])
                if show_all else root['tables']
            )
            return [
                {
                    'name': table['name'],
                    'type': 'table',
                    'columns': len(table['columns']),
                    'rows': table.get('row_count'),
                    'size': table.get('size', '-'),
                }
                for table in tables
            ]
        names = (
            root.get('all_table_names', root['table_names'])
            if show_all else root['table_names']
        )
        return [
            {'name': name, 'type': 'table'}
            for name in names
        ]
    raise ValueError('Cannot list root type {!r}'.format(root.get('type')))


def _value_key(value):
    try:
        hash(value)
    except TypeError:
        return type(value), repr(value)
    return type(value), value


def _profile_table(table, limit):
    if limit <= 0:
        raise ValueError('scan limit must be greater than zero')

    known_count = table.get('row_count')

    columns = tuple(table['columns'])
    profiles = [
        {
            'name': name,
            'data_types': [],
            'cardinality': set(),
            'max_width': 0,
            'observed_keys': set(),
            'observed': [],
        }
        for name in columns
    ]
    rows = iter(table['rows'])
    rows_scanned = 0
    exhausted = False
    try:
        for _ in range(limit):
            try:
                row = next(rows)
            except StopIteration:
                exhausted = True
                break
            for index, name in enumerate(columns):
                value = row.get(name) if hasattr(row, 'get') else row[index]
                profile = profiles[index]
                type_name = TYPE_NAMES.get(type(value), type(value).__name__)
                if type_name not in profile['data_types']:
                    profile['data_types'].append(type_name)
                key = _value_key(value)
                profile['cardinality'].add(key)
                profile['max_width'] = max(profile['max_width'], len(str(value)))
                if key not in profile['observed_keys'] and len(profile['observed']) < 16:
                    profile['observed_keys'].add(key)
                    profile['observed'].append(value)
            rows_scanned += 1
    finally:
        close = getattr(rows, 'close', None)
        if close is not None:
            close()

    if known_count is not None:
        sampled = rows_scanned < known_count
        row_count = known_count
    else:
        sampled = not exhausted
        row_count = None if sampled else rows_scanned

    result_columns = []
    for profile in profiles:
        result_columns.append({
            'name': profile['name'],
            'data_types': tuple(profile['data_types']),
            'cardinality': len(profile['cardinality']),
            'max_width': profile['max_width'],
            'observed': tuple(profile['observed']),
        })

    return {
        'name': table['name'],
        'row_count': row_count,
        'rows_scanned': rows_scanned,
        'sampled': sampled,
        'columns': result_columns,
    }


def scan(root, limit=100000):
    """Profile tables directly from rooted Connector output."""
    if root.get('type') in ('table', 'column'):
        tables = (root,)
    elif root.get('type') == 'database':
        tables = root['tables']
    else:
        raise ValueError('Cannot scan root type {!r}'.format(root.get('type')))
    return [
        _profile_table(table, limit)
        for table in tables
    ]
