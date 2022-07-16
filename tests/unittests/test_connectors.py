"""
    connector tests
"""

import unittest

import gitdata.connectors
from gitdata.connectors.common import get
from gitdata.connectors import extract

# class TestConnectors(unittest.TestCase):

#     def test_get_connectors(self):
#         connectors = list(gitdata.connectors.common.get_connectors())
#         self.assertGreater(len(connectors), 0)

#     def test_connect(self):
#         system = gitdata.connect('system')
#         self.assertEqual(system.name, platform.node())


class TestBaseConnector(unittest.TestCase):

    def tearDown(self):
        connector = gitdata.connectors.common.BaseConnector()
        connector.reads = []
        connector.writes = []

    def test_no_edges(self):
        connector = gitdata.connectors.common.BaseConnector()
        self.assertEqual(
            list(connector.edges),
            []
        )

    def test_one_edge(self):
        Connector = gitdata.connectors.common.BaseConnector
        Connector.reads = ['file']
        Connector.writes = ['blob']
        connector = Connector()
        self.assertEqual(
            list(connector.edges),
            [('file', 'blob')]
        )

    def test_writes_two(self):
        Connector = gitdata.connectors.common.BaseConnector
        Connector.reads = ['file']
        Connector.writes = ['blob', 'name']
        connector = Connector()
        self.assertEqual(
            list(connector.edges),
            [('file', 'blob'), ('file', 'name')]
        )

    def test_reads_two(self):
        Connector = gitdata.connectors.common.BaseConnector
        Connector.reads = ['https', 'ftp']
        Connector.writes = ['blob']
        connector = Connector()
        self.assertEqual(
            list(connector.edges),
            [('https', 'blob'), ('ftp', 'blob')]
        )

    def test_reads_writes_two(self):
        Connector = gitdata.connectors.common.BaseConnector
        Connector.reads = ['https', 'ftp']
        Connector.writes = ['blob', 'status']
        connector = Connector()
        self.assertEqual(
            list(connector.edges),
            [
                ('https', 'blob'), ('https', 'status'),
                ('ftp', 'blob'), ('ftp', 'status')
            ]
        )


# class TestSystemConnector(unittest.TestCase):

#     def test_name(self):
#         c = gitdata.connectors.connect('system')
#         print(c)
#         self.assertEqual(c.name, platform.node())


# class TestStandardConnectors(unittest.TestCase):

#     def test_csv_edges(self):
#         edges = gitdata.connectors.common.get_connector_graph()
#         self.assertIn(('console', 'text', 'stdout'), edges)

class People(gitdata.utils.RecordList):

    @property
    def sex(self):
        return [
            p['sex']
            for p in self
        ]


class Addresses(gitdata.utils.RecordList):
    pass


def expecting_in(values, allowed):
    return all(v in allowed for v in values)


def limit(count, iterator):
    """Grab at most count items from iterator"""
    for item in iterator:
        yield item
        count -= 1
        if not count:
            break


class TestFake(unittest.TestCase):

    def test_people(self):
        fake = get('fake')
        people = People(limit(20, fake['people']))
        self.assertTrue(
            expecting_in(people.sex, ['M', 'F'])
        )
        self.assertEqual(len(people), 20)

    def test_addresses(self):
        fake = get('fake')
        addresses = Addresses(limit(10, fake['addresses']))
        self.assertEqual(len(addresses), 10)


class TestExtract(unittest.TestCase):

    def test_extract_csv(self):
        t = extract('examples/locations.csv')
        # self.assertEqual(t.filename, 'locations.csv')
