"""Read-only consumers of rooted Connector output."""

from datetime import date, datetime
from decimal import Decimal


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


def list_items(root, verbose=False):
    """Describe the immediate children of a supported root."""
    if root.get('type') == 'server':
        if verbose and 'database_summaries' in root:
            return list(root['database_summaries'])
        return [
            {'name': name, 'type': 'database'}
            for name in root['database_names']
        ]
    if root.get('type') == 'column':
        return []
    if root.get('type') == 'table':
        if verbose and 'column_summaries' in root:
            return list(root['column_summaries'])
        return [
            {'name': name, 'type': 'column'}
            for name in root['columns']
        ]
    if root.get('type') == 'database':
        if verbose and 'table_summaries' in root:
            return list(root['table_summaries'])
        if verbose:
            return [
                {
                    'name': table['name'],
                    'type': 'table',
                    'columns': len(table['columns']),
                    'rows': table.get('row_count'),
                    'size': table.get('size', '-'),
                }
                for table in root['tables']
            ]
        return [
            {'name': name, 'type': 'table'}
            for name in root['table_names']
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
