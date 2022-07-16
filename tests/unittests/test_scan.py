"""
    datascan tests
"""

from decimal import Decimal
import unittest

from gitdata.graphs import Graph


def scan(g):

    for table in g.find('name', isa='table'):

        print('Table:', table['name'])

        columns = [r['column'] for r in g.query(
            [
                (table['columns'], 'includes', '?column')
            ]
        )]

        rows = [r['row'] for r in g.query(
            [
                (table['rows'], 'includes', '?row')
            ]
        )]
        print(rows)

        for n, column in enumerate(columns):
            print(n, column)


class TestScan(unittest.TestCase):

    def test_small(self):

        data = {
            'name': 'mytable',
            'isa': 'table',
            'columns': [
                'name',
                'address',
                'age',
                'salary',
            ],
            'rows': [
                ('Joe', '1000 Somewhere St', 10, Decimal(10000)),
                ('Pat', '2000 Somewhere St', 20, Decimal(20000)),
                ('Kim', '3000 Somewhere St', 30, Decimal(30000)),
                ('Sam', '4000 Somewhere St', 40, Decimal(40000)),
            ]
        }

        g = Graph()
        g.add(data)
        # print(g)

        print(scan(g))
