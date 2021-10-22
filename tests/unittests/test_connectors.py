"""
    connector tests
"""

import platform
import unittest

import gitdata.connectors


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
