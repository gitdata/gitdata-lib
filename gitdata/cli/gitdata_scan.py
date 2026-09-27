"""
usage: gitdata scan [options] <ref>...

options:
    --limit=<n>, -n <n>     maximum rows sampled per table [default: 100000]
    -h, --help              show help
"""

from gitdata.connectors import fetch
from gitdata.inspection import scan


def _title(report):
    columns = len(report['columns'])
    if report['row_count'] is None:
        rows = 'at least {:,}'.format(report['rows_scanned'])
    else:
        rows = '{:,}'.format(report['row_count'])
    sampled = ' (sampled)' if report['sampled'] else ''
    return '{}: {:,} columns, {} rows{}'.format(
        report['name'], columns, rows, sampled
    )


def _format_value(value):
    return 'None' if value is None else str(value)


def _print_report(report):
    print(_title(report))
    print('Column\tData Types\tCardinality\tSize\tObserved Values')
    for column in report['columns']:
        cardinality = '{:,}'.format(column['cardinality'])
        if report['sampled']:
            cardinality = '~' + cardinality
        print('{}\t{}\t{}\t{}\t{}'.format(
            column['name'],
            ', '.join(column['data_types']),
            cardinality,
            column['max_width'],
            ', '.join(_format_value(value) for value in column['observed']),
        ))


def scan_to_console(args):
    """Profile refs directly from Connector output."""
    limit = int(args['--limit'])
    first = True
    for ref in args['<ref>']:
        for report in scan(fetch(ref), limit=limit):
            if not first:
                print()
            first = False
            _print_report(report)
