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
        report['name'], columns, column_label, rows, row_label, sampled
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
    if len(text) > 12:
        return text[:12] + '...'
    return text


def _column_widths():
    terminal = shutil.get_terminal_size((120, 24)).columns
    types_width = 12
    cardinality_width = 11
    size_width = 8
    name_preferred = 30
    name_minimum = 20
    observed_minimum = 20
    leftover = terminal - (
        types_width + cardinality_width + size_width + 5
    )
    name_width = name_preferred
    observed_width = leftover - name_width
    if observed_width < observed_minimum:
        name_width = max(name_minimum, leftover - observed_minimum)
        observed_width = leftover - name_width
    if observed_width < observed_minimum:
        observed_width = observed_minimum
    return (
        name_width,
        types_width,
        cardinality_width,
        size_width,
        observed_width,
    )


def _cell(value, width, right=False):
    text = str(value)
    if len(text) > width:
        half = round(width / 2)
        text = (text[:half - 2] + ' ... ' + text[-half + 3:])[:width]
    if right:
        return text.rjust(width)
    return text.ljust(width)


def _row(values, widths, right_aligned):
    return ' '.join(
        _cell(value, width, right)
        for value, width, right in zip(values, widths, right_aligned)
    ).rstrip()


def _print_report(report):
    print(_title(report))
    widths = _column_widths()
    alignment = (False, False, True, True, False)
    labels = (
        'Columns',
        'Data Types',
        'Cardinality',
        'Size',
        'Observed Values',
    )
    print(_row(labels, widths, alignment))
    print(_row(('-' * width for width in widths), widths, (False,) * 5))
    for column in report['columns']:
        cardinality = '{:,}'.format(column['cardinality'])
        if report['sampled']:
            cardinality = '~' + cardinality
        print(_row(
            (
                column['name'],
                ', '.join(column['data_types']),
                cardinality,
                '{:,}'.format(column['max_width']),
                ', '.join(
                    _format_value(value)
                    for value in column['observed']
                ),
            ),
            widths,
            alignment,
        ))


def scan_to_console(args):
    """Profile refs directly from Connector output."""
    limit = int(args['--limit'])
    first = True
    for ref in args['<ref>']:
        for report in scan(
                fetch(ref, count_rows=not args['--no-count']),
                limit=limit):
            if not first:
                print()
            first = False
            _print_report(report)
