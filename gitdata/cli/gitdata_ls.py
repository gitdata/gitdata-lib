"""
usage: gitdata ls [options] <ref>

options:
    --long, -l      use a long listing format
    --all, -a       include database-specific system objects
    -h, --help      show help
"""

from gitdata.cli import terminal_text
from gitdata.connectors import fetch
from gitdata.inspection import list_items


_LAYOUTS = {
    'server': (
        ('Database', 'Tables', 'Rows', 'Size (MB)'),
        ('name', 'tables', 'rows', 'size'),
        (35, 10, 15, 10),
    ),
    'database': (
        ('Table', 'Columns', 'Rows', 'Size (MB)'),
        ('name', 'columns', 'rows', 'size'),
        (35, 10, 15, 10),
    ),
    'table': (
        ('Column', 'Type', 'Null', 'Key', 'Default', 'Extra'),
        ('name', 'data_type', 'null', 'key', 'default', 'extra'),
        (24, 20, 5, 5, 22, 16),
    ),
}


_NUMERIC_KEYS = frozenset(('tables', 'columns', 'rows', 'size'))


def _display(value):
    if value is None:
        return '-'
    if isinstance(value, int):
        return '{:,}'.format(value)
    return terminal_text(value)


def _row(values, widths, right_aligned=()):
    return ' '.join(
        (
            _display(value).rjust(width)
            if index in right_aligned
            else _display(value).ljust(width)
        )
        for index, (value, width) in enumerate(zip(values, widths))
    ).rstrip()


def _print_verbose(root, items):
    labels, keys, widths = _LAYOUTS.get(
        root['type'], (('Name', 'Type'), ('name', 'type'), (35, 12))
    )
    if root.get('item_label'):
        labels = (root['item_label'],) + labels[1:]
    numeric_columns = frozenset(
        index for index, key in enumerate(keys) if key in _NUMERIC_KEYS
    )
    print(_row(labels, widths, numeric_columns))
    print(_row(('-' * width for width in widths), widths, numeric_columns))
    for item in items:
        print(_row(
            (item.get(key, '-') for key in keys),
            widths,
            numeric_columns,
        ))

    indexes = list(root.get('indexes', ()))
    if indexes:
        print()
        index_labels = ('Index', 'Unique', 'Columns')
        index_keys = ('name', 'unique', 'columns')
        index_widths = (32, 6, 40)
        print(_row(index_labels, index_widths))
        print(_row(('-' * width for width in index_widths), index_widths))
        for index in indexes:
            print(_row(
                (index.get(key, '-') for key in index_keys),
                index_widths,
            ))


def ls_to_console(args):
    """List immediate children directly from Connector output."""
    verbose = args['--long']
    show_all = args['--all']
    root = fetch(args['<ref>'], count_rows=False)
    items = list_items(root, verbose=verbose, show_all=show_all)
    if verbose:
        if root['type'] == 'column':
            return
        _print_verbose(root, items)
        return
    for item in items:
        print(terminal_text(item['name']))
