"""
usage: gitdata ls [options] <ref>

options:
    --long, -l      use a long listing format
    --all, -a       include database-specific system objects
    -h, --help      show help
"""

import shutil

from gitdata.cli import terminal_text
from gitdata.cli.terminal_width import align_text, display_width, fit_text
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
    'csv': (
        (
            'Column', 'Type', 'Empty', 'Distinct',
            'Key?', 'Width', 'Example',
        ),
        (
            'name', 'data_type', 'empty', 'distinct',
            'candidate_key', 'width', 'example',
        ),
        (20, 10, 8, 10, 5, 7, 20),
    ),
}


_ITEM_LABELS = {
    'server': 'database',
    'database': 'table',
    'table': 'column',
}


_NUMERIC_KEYS = frozenset((
    'tables', 'columns', 'rows', 'size', 'empty', 'distinct', 'width',
))


def _display(value):
    if value is None:
        return '-'
    if isinstance(value, int):
        return '{:,}'.format(value)
    return terminal_text(value)


def _fit(value, width):
    return fit_text(_display(value), width).rstrip()


def _row(values, widths, right_aligned=()):
    return ' '.join(
        align_text(_display(value), width, index in right_aligned)
        for index, (value, width) in enumerate(zip(values, widths))
    ).rstrip()


def _terminal_width():
    return max(1, shutil.get_terminal_size((120, 24)).columns)


def _bounded_widths(labels, keys, widths, items, terminal_width):
    preferred = [
        max(
            width,
            display_width(_display(label)),
            max(
                (
                    display_width(_display(item.get(key, '-')))
                    for item in items
                ),
                default=0,
            ),
        )
        for label, key, width in zip(labels, keys, widths)
    ]
    minimum = [max(1, display_width(_display(label))) for label in labels]
    overflow = sum(preferred) + len(preferred) - 1 - terminal_width
    priorities = [
        index for key in (
            'example', 'extra', 'default', 'columns', 'name', 'data_type',
        )
        for index, candidate in enumerate(keys)
        if candidate == key
    ]
    priorities.extend(
        index for index in reversed(range(len(preferred)))
        if index not in priorities
    )
    for index in priorities:
        if overflow <= 0:
            break
        reduction = min(overflow, preferred[index] - minimum[index])
        preferred[index] -= reduction
        overflow -= reduction
    if overflow > 0:
        for index in sorted(
                range(len(preferred)),
                key=lambda candidate: preferred[candidate],
                reverse=True):
            if overflow <= 0:
                break
            reduction = min(overflow, preferred[index] - 1)
            preferred[index] -= reduction
            overflow -= reduction
    return tuple(preferred)


def _print_verbose(root, items):
    terminal_width = _terminal_width()
    layout = root.get('format', root['type'])
    labels, keys, widths = _LAYOUTS.get(
        layout, (('Name', 'Type'), ('name', 'type'), (35, 12))
    )
    if root.get('item_label'):
        labels = (root['item_label'],) + labels[1:]
    widths = _bounded_widths(
        labels, keys, widths, items, terminal_width
    )
    numeric_columns = frozenset(
        index for index, key in enumerate(keys) if key in _NUMERIC_KEYS
    )
    print(_fit(_row(labels, widths, numeric_columns), terminal_width))
    print(_fit(
        _row(('-' * width for width in widths), widths, numeric_columns),
        terminal_width,
    ))
    for item in items:
        print(_fit(_row(
            (item.get(key, '-') for key in keys),
            widths,
            numeric_columns,
        ), terminal_width))

    indexes = list(root.get('indexes', ()))
    if indexes:
        print()
        index_labels = ('Index', 'Unique', 'Columns')
        index_keys = ('name', 'unique', 'columns')
        index_widths = _bounded_widths(
            index_labels,
            index_keys,
            (32, 6, 40),
            indexes,
            terminal_width,
        )
        print(_fit(_row(index_labels, index_widths), terminal_width))
        print(_fit(
            _row(('-' * width for width in index_widths), index_widths),
            terminal_width,
        ))
        for index in indexes:
            print(_fit(_row(
                (index.get(key, '-') for key in index_keys),
                index_widths,
            ), terminal_width))


def _print_count(root, count):
    label = (
        root.get('item_label') or _ITEM_LABELS[root['type']]
    ).lower()
    if count != 1:
        label += 's'
    print(_fit('{} {}'.format(count, label), _terminal_width()))


def ls_to_console(args):
    """List immediate children directly from Connector output."""
    verbose = args['--long']
    show_all = args['--all']
    root = fetch(args['<ref>'], count_rows=False)
    items = list_items(root, verbose=verbose, show_all=show_all)
    if root['type'] == 'column':
        return
    if verbose:
        _print_verbose(root, items)
        _print_count(root, len(items))
        return
    terminal_width = _terminal_width()
    for item in items:
        print(_fit(item['name'], terminal_width))
    _print_count(root, len(items))
