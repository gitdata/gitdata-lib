"""
    gitdata repository tests
"""
# pylint: disable=missing-docstring, no-member

import os
import time

import unittest
import gitdata.repositories


class RepositorySuite:

    # def setUp(self):
    #     self.repository = gitdata.repositories.Repository()

    def test_fetch_nothing(self):
        self.assertIsNone(self.repository.fetch('examples/not_a_file.json'))

    def test_fetch(self):
        self.repository.fetch('examples/miserables.json')
        # print(self.repository.graph.db('select * from facts'))
        # print(facts)

    def test_facts(self):
        repository = self.repository
        repository.fetch('examples/miserables.json')
        result = repository.graph.facts.triples((None, 'filename', None))
        _, _, filename = list(result)[0]
        self.assertEqual(filename, 'miserables.json')


class TestLocalRepositorySetup(unittest.TestCase):

    def test_init(self):
        working_directory = 'tmp'
        path = working_directory + '/.gitdata'
        if os.path.isdir(path):
            os.rmdir(path)
        self.assertFalse(os.path.exists(path))
        gitdata.repositories.create_respository(working_directory)
        try:
            repository = gitdata.repositories.Repository(working_directory)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.exists(path + '/facts'))
        finally:
            del repository
            gitdata.repositories.remove_respository(working_directory)


class TestLocalRepository(RepositorySuite, unittest.TestCase):

    def setUp(self):
        self.working_directory = working_directory = 'tmp'
        gitdata.repositories.remove_respository(working_directory)
        if not os.path.exists(working_directory):
            os.mkdir(working_directory)
        gitdata.repositories.create_respository(working_directory)
        self.repository = gitdata.repositories.Repository(working_directory)
        print(os.listdir('tmp/.gitdata'))
        self.repository.fetch('examples/miserables.json')

    def tearDown(self):
        gitdata.repositories.remove_respository(self.working_directory)


class TestMemoryRepository(RepositorySuite, unittest.TestCase):

    def setUp(self):
        self.repository = gitdata.repositories.Repository()
