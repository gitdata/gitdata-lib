"""
    gitdata repositories
"""

import datetime
import getpass
import logging
import os
import platform

from gitdata.connectors.common import (
    get
)
from gitdata.graphs import Graph
from gitdata.utils import parents


logger = logging.getLogger(__name__)


def locate_repository(dirname='.gitdata', start='.'):
    """locate a gitdata repository

    First look in the current directory or above and then look
    in the user root directory and above.
    """
    for path in parents(start):
        pathname = os.path.join(path, dirname)
        if os.path.exists(pathname):
            return pathname


def create_respository(pathname):
    """Create a new GitData repository"""
    if os.path.isdir(pathname):
        init_repository(pathname)


def init_repository(pathname='.'):
    """Initialize a GitData repository and return path + created flag."""
    if os.path.isdir(pathname):
        repository_path = os.path.join(pathname, '.gitdata')
    else:
        repository_path = pathname
        parent = os.path.dirname(os.path.abspath(repository_path)) or '.'
        if not os.path.isdir(parent):
            msg = 'directory does not exist: {!r}'
            raise ValueError(msg.format(parent))

    if os.path.exists(repository_path):
        return repository_path, False

    repository = Repository(repository_path)
    repository.setup()
    return repository_path, True


def remove_respository(pathname):
    """Remove GitData repository"""
    if os.path.isdir(pathname):
        repository_path = os.path.join(pathname, '.gitdata')
        if os.path.isfile(repository_path):
            os.remove(repository_path)


def add_connection_metadata(facts, **kwargs):
    facts.update(
        dict(
            pulled=datetime.datetime.now(),
            node=platform.node(),
            user=getpass.getuser(),
            **kwargs
        )
    )


class Repository:
    """Gitdata Repository"""

    def __init__(self, location=':memory:'):
        if location == ':memory:':
            self.location = location
        elif os.path.isdir(location):
            self.location = os.path.join(location, '.gitdata')
        else:
            self.location = location
        self.graph = Graph(self.location)

    def __del__(self):
        del self.graph

    def setup(self):
        self.graph.setup()

    def fetch(self, ref):
        """Fetch a ref"""
        data = get(ref)
        self.graph.add(data)
        return data

        # self.facts = digested(facts)
        # for fact in self.facts:
        #     print(fact)
        #     if isinstance(fact[2], io.BytesIO):
        #         print('blob was found')
        #         print(dir(fact[2]))
        #     # if hasattr(fact, io.BytesIO):
        #     #     print('blob was found')

        # if self.facts:
        #     print(undigested(self.facts))

        # # print(len(facts), 'facts')
        # return facts

        # connectors = get_connectors()
        # for connector in connectors:
        #     if hasattr(connector, 'get'):
        #         facts = connector().get(ref)
        #         if facts:
        #             add_connection_metadata(facts, ref=ref)
        #             return facts

        # uid = self.graph.put(
        #     stack.fetch(ref)
        # )
