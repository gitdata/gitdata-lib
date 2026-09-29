"""
    common connector
"""

import datetime
import getpass
import inspect
import importlib
import io
import logging
import os
import pkgutil
import platform

import gitdata.connectors
import gitdata.ext.connectors
import gitdata.graphs
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


class ConnectorError(Exception):
    """Raised when a Connector cannot complete an expected operation."""


class UnsupportedRef(ValueError):
    """Raised when no Connector can resolve a ref."""


def password_from_environment(database, error_type=ValueError):
    """Read a database password through the configured environment variable."""
    variable = os.environ.get('GITDATA_PASSWORD_ENV', 'PASSWORD')
    if not variable:
        raise error_type(
            'GITDATA_PASSWORD_ENV must name an environment variable'
        )
    try:
        return os.environ[variable]
    except KeyError:
        raise error_type(
            '{} password environment variable {!r} is not set'.format(
                database, variable
            )
        ) from None


class Blob(io.BytesIO):
    """Blob"""

    def __str__(self):
        return '{:,} bytes'.format(len(self))

    def __len__(self):
        return self.getbuffer().nbytes


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

    def extract(self, ref):
        """Extract facts from a ref"""

    def get_tables(self):
        return []

    def get_blobs(self):
        return []

    # def explore(self, data):
    #     """Explore a graph
    #     """
    #     print('exploring ', data)


def connect(ref):
    """Return a connection to a ref"""

    for connector in get_connectors():
        connection = connector().connect(ref)
        if connection:
            return connection


    # connectors = {
    #     connector.__name__: connector for connector in get_connectors()}

    # if 'System' in connectors:
    #     return connectors['System']()

def add_connection_metadata(facts):
    facts.update(
        dict(
            collected=datetime.datetime.now(),
            node=platform.node(),
            user=getpass.getuser()
        )
    )


def fetch(ref, count_rows=True):
    """Resolve one ref through the Connector chain into one Python root."""
    for connector_type in get_connectors():
        connector = connector_type()
        resolve = getattr(connector, 'fetch', None)
        if resolve is None:
            continue
        parameters = inspect.signature(resolve).parameters.values()
        supports_options = any(
            parameter.name == 'count_rows'
            or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        if supports_options:
            result = resolve(ref, count_rows=count_rows)
        else:
            result = resolve(ref)
        if result is not None:
            return result
    raise UnsupportedRef('No Connector accepts {!r}'.format(ref))

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

class Bunch:
    """a handy bunch of variables"""
    tables = []

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __str__(self):
        return f'{self.__class__.__name__}\n' + '\n  '.join(
            f'{k:{(20-len(k))*"."}}: {v!r}'
            for k, v in self.__dict__.items()
        )

class State(dict):
    """State of Extraction"""

    def find(self, kind):
        """Return things of a kind"""
        cache = self.setdefault('_cache', [])
        for thing in self.setdefault(kind, []):
            thing_id = id(thing)
            if thing_id not in cache:
                cache.append(thing_id)
                yield thing

    def add(self, kind, value):
        """Add a value of a certain kind"""
        self.setdefault(kind, []).append(value)


def extract(ref):
    """Extract a reference

    Extract data from a reference.
    """

    connectors = get_connectors()

    # ref = State(ref=refs)

    extracting = True
    while extracting:
        extracting = any(
            connector().extract(ref)
            for connector in connectors
        )
        # print(extracting)

    return Bunch(
        # name=ref.get('name', ref['ref']),
        # ref=ref['ref'],
        # tables=ref['tables'],
        # text=ref['text'],
    )


def load(ref):
    """Get a Graph
    """
    graph = gitdata.graphs.Graph()
    graph.add(get(ref))
    return graph
