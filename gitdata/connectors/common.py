"""
    common connector
"""

import datetime
import getpass
import inspect
import importlib
import logging
import pkgutil
import platform

import gitdata.connectors
import gitdata.ext.connectors
import gitdata.solutions


logger = logging.getLogger(__name__)


def get_connectors():
    """generate connectors"""
    path = gitdata.connectors.__path__

    for _, name, _ in pkgutil.iter_modules(path):
        if name != 'common':
            module = importlib.import_module('gitdata.connectors.' + name)
            for _, obj in inspect.getmembers(module):
                if obj == BaseConnector:
                    continue
                try:
                    found = issubclass(obj, BaseConnector)
                except TypeError:
                    found = False
                if found:
                    yield obj

    path = gitdata.ext.connectors.__path__
    for _, name, _ in pkgutil.iter_modules(path):
        module = importlib.import_module('gitdata.ext.connectors.' + name)
        for _, obj in inspect.getmembers(module):
            if obj == BaseConnector:
                continue
            try:
                found = issubclass(obj, BaseConnector)
            except TypeError:
                found = False
            if found:
                yield obj


def get_connector_graph():
    """generate connector graph"""
    edges = []
    for connector in get_connectors():
        for reads, writes in connector.get_edges():
            edges.append((connector.name, reads, writes))
    return sorted(edges, key=lambda a: a[1:])


def explore(node, destination):
    """Explore a location

    Explore a location by finding the next step in all possible
    outgoing routes and exploring them.
    """

    location = node['location']
    logger.debug('exploring location %s to %s', location, destination)
    logger.debug('exploring location %r', node)

    connectors = get_connector_graph()
    # logger.debug('connectors:')
    # for connector in connectors:
    #     logger.debug('  %s via %s', connector[1:], connector[0])

    edges = [(a, b) for _, a, b in connectors]
    cost = lambda *_: 1
    planner = gitdata.solutions.Pathfinder(edges, cost)
    logger.debug('planning routes')
    for n, route in enumerate(planner.find('location', destination)):
        logger.debug('route %-2d: %s', n, route)

    # logger.debug(node.graph)

        # print('    running', route[0])

        # for segment in route:
        #     print('    running', segment)

    # print(planner.find('location', destination))


# def get_edges(connector):
#         for a in connector.reads:
#             for b in connector.writes:
#                 yield a, b


class BaseConnector:
    """BaseConnector"""

    reads = []
    writes = []

    @classmethod
    def get_edges(cls):
        """Return connector graph edges"""
        for a in cls.reads:
            for b in cls.writes:
                yield a, b

    @property
    def edges(self):
        """Connector graph edges"""
        return self.get_edges()

    def connects(self, ref):
        """Return True if connector connects to ref"""

    def connect(self, ref):
        """Connect to a ref"""

    # def explore(self, data):
    #     """Explore a graph
    #     """
    #     print('exploring ', data)


def connect(ref):
    """Return a connection to a ref"""

    for connector in get_connectors():
        if connector.connects(ref):
            connection = connector()
            connection.connect(ref)
            return connection


    # connectors = {
    #     connector.__name__: connector for connector in get_connectors()}



    # if 'System' in connectors:
    #     return connectors['System']()

def add_connection_metadata(facts):
    facts.update(
        dict(
            pulled=datetime.datetime.now(),
            node=platform.node(),
            user=getpass.getuser()
        )
    )


def fetch(ref):
    """Fetch data

    Fetch the facts in a datasource and store them.
    """
    connectors = get_connectors()
    for connector in connectors:
        if hasattr(connector, 'get'):
            facts = connector().get(ref)
            if facts:
                add_connection_metadata(facts)
                return facts

def get(ref):
    """Get Data

    Get the facts from a datasource.
    """
    connectors = get_connectors()
    for connector in connectors:
        if hasattr(connector, 'get'):
            facts = connector().get(ref)
            if facts:
                add_connection_metadata(facts)
                return facts
