"""
usage: gitdata scan [options] <ref>...

options:
    --limit=<n>, -n <n>     maximum rows sampled per table [default: 100000]
    --no-count              skip the eager database COUNT(*) query
    -h, --help              show help
"""

from datetime import date, datetime
from decimal import Decimal
import shutil
import sys

from gitdata.cli import terminal_text
from gitdata.cli.terminal_width import align_text, display_width, fit_text
from gitdata.connectors import fetch
from gitdata.inspection import scan


def _title(report):
    columns = len(report['columns'])
    if report['row_count'] is None:
        rows = 'at least {:,}'.format(report['rows_scanned'])
    else:
        rows = '{:,}'.format(report['row_count'])
    sampled = ' (sampled)' if report['sampled'] else ''
    column_label = 'column' if columns == 1 else 'columns'
    row_label_count = (
        report['row_count']
        if report['row_count'] is not None
        else report['rows_scanned']
    )
    row_label = 'row' if row_label_count == 1 else 'rows'
    return '{}: {:,} {}, {} {}{}'.format(
        terminal_text(report['name']),
        columns,
        column_label,
        rows,
        row_label,
        sampled,
    )


def _format_value(value):
    if value is None:
        text = 'None'
    elif isinstance(value, float):
        text = '{:.3f}'.format(value)
    elif isinstance(value, Decimal):
        text = '{:.2f}'.format(value)
    elif isinstance(value, datetime):
        text = '{:%Y-%m-%d %H:%M:%S}'.format(value)
    elif isinstance(value, date):
        text = '{:%Y-%m-%d}'.format(value)
    else:
        text = str(value)
    return terminal_text(text)


def _column_widths(rows):
    terminal = max(1, shutil.get_terminal_size((120, 24)).columns)
    labels = (
        'Columns', 'Data Types', 'Cardinality', 'Size', 'Observed Values',
    )
    preferred = [
        max(
            width,
            display_width(label),
            max(
                (display_width(row[index]) for row in rows),
                default=0,
            ),
        )
        for index, (label, width) in enumerate(zip(
            labels, (30, 12, 11, 8, 20)
        ))
    ]
    minimum = [display_width(label) for label in labels]
    overflow = sum(preferred) + len(preferred) - 1 - terminal
    for index in (4, 0, 1, 2, 3):
        if overflow <= 0:
            break
        reduction = min(overflow, preferred[index] - minimum[index])
        preferred[index] -= reduction
        overflow -= reduction
    if overflow > 0:
        for index in (4, 0, 1, 2, 3):
            if overflow <= 0:
                break
            reduction = min(overflow, preferred[index] - 1)
            preferred[index] -= reduction
            overflow -= reduction
    return tuple(preferred)


def _cell(value, width, right=False):
    return align_text(value, width, right)


def _row(values, widths, right_aligned):
    return ' '.join(
        _cell(value, width, right)
        for value, width, right in zip(values, widths, right_aligned)
    ).rstrip()


def _print_report(report):
    labels = (
        'Columns',
        'Data Types',
        'Cardinality',
        'Size',
        'Observed Values',
    )
    rows = []
    for column in report['columns']:
        cardinality = '{:,}'.format(column['cardinality'])
        if report['sampled']:
            cardinality = '~' + cardinality
        rows.append((
            terminal_text(column['name']),
            terminal_text(', '.join(column['data_types'])),
            cardinality,
            '{:,}'.format(column['max_width']),
            terminal_text(', '.join(
                _format_value(value)
                for value in column['observed']
            )),
        ))
    widths = _column_widths(rows)
    terminal_width = max(1, shutil.get_terminal_size((120, 24)).columns)
    print(fit_text(_title(report), terminal_width).rstrip())
    alignment = (False, False, True, True, False)
    print(fit_text(_row(labels, widths, alignment), terminal_width).rstrip())
    print(fit_text(
        _row(('-' * width for width in widths), widths, (False,) * 5),
        terminal_width,
    ).rstrip())
    for row in rows:
        print(fit_text(_row(row, widths, alignment), terminal_width).rstrip())


def scan_to_console(args):
    """Profile refs directly from Connector output."""
    limit = int(args['--limit'])
    first = True
    for ref in args['<ref>']:
        root = fetch(ref, count_rows=not args['--no-count'])
        if root.get('type') == 'server':
            raise SystemExit(
                'gitdata scan: please supply a database name, for example '
                'mysql://host/database; use gitdata ls on the server ref to '
                'list visible databases'
            )
        print('Scanning...', file=sys.stderr, flush=True)
        for report in scan(root, limit=limit):
            if not first:
                print()
            first = False
            _print_report(report)
