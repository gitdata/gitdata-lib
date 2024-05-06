"""
usage: gitdata scan [options] [<ref>...]

options:
    --limit <n>, -n <n>     limit number of records displayed
    --name-columns          provide synthetic column names (handy for csv files that do not provide a header)
    -h, --help
"""

import csv
import os

import gitdata
from gitdata.connectors.common import load, connect, get_connectors
from gitdata.connectors.http import HttpConnector


def as_blobs(ref):
    if os.path.isfile(ref):
        with open(ref, 'rb') as f:
            return [f.read()]

    if ref.startswith('http'):
        http_connector = HttpConnector()
        result = http_connector.get(ref)
        if result:
            return [result['blob'].read()]

    return []


def as_tables(ref, args):
    for blob in as_blobs(ref):
        rows = []
        try:
            reader = csv.reader(blob.decode('utf8').splitlines())
        except UnicodeDecodeError:
            reader = csv.reader(blob.decode('Latin1').splitlines())
        for row in reader:
            rows.append(row)
        yield gitdata.Record(
            name=ref,
            filename=ref,
            rows=rows,
            columns=[gitdata.Record(name=f'{chr(n+65)}', type='str') for n in range(len(rows[0]))]
        )


def scan(ref, args):

    def scan_table(table):
        header = gitdata.Record(
            name=table.name,
            row_count=len(table.rows),
            column_count=len(table.rows[0])
        )

        limit = args['--limit'] and int(args['--limit']) or 5

        if args['--name-columns']:
            rows = [[t.name for t in table.columns]] + table.rows[:limit]
        else:
            rows = table.rows[:limit]

        sample = gitdata.utils.ItemList(rows)
        return str(header) + '\n' + str(sample) + str(list())

    return ''.join(scan_table(table) for table in as_tables(ref, args))


# class Scanner:

#     def __init__(self, ref, args):
#         self.ref = ref
#         self.args = args

#     def __str__(self):
#         result = [f'Scan: {self.ref}']
#         for table in tables(self.ref):
#             result.append(f'Table: {table.name}')

class MegaConnect:

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    @property
    def tables(self):
        
        for connector in get_connectors():
            if 'table' in connector.writes:
                print(connector.reads)

        for name in ['one', 'two']:
            yield name


def connect2(ref):
    # for connector in get_connectors():
    #     print(connector, connector.reads, connector.writes)
    # print(ref)
    # print([f for f in [dir(x) for x in get_connectors()]][0])
    return MegaConnect(ref)


def scan_table(table):
    return str(table)


def scan2(connection):
    result = []
    for table in connection.tables:
        result.append(scan_table(table))
        # for row in table:
        #     for value in row:
    return '\n'.join(result)


def console(output):
    if output:
        print(output)


def scan_to_console(args):
    if args['<ref>']:
        for ref in args['<ref>']:
            connection = connect2(ref)
            console(scan2(connection))
            # console(Scanner(ref, args))
            # connection = connect(ref)
            # if connection:
            #     print(connection)
            #     for table in connection.get_tables():
            #         print(f'scanning {table.name}')
            # else:
            #     print(f'unable to connect to {ref}')

            # g = load(ref)
            # print('scanning', ref)
            # print(repr(g))
            # print(g)
    else:
        print(__doc__)
