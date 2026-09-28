"""
    gitdata repository tests
"""
# pylint: disable=missing-docstring, no-member

import os
import tempfile
import unittest

import gitdata.repositories


class RepositorySuite:

    def test_fetch_nothing(self):
        self.assertIsNone(self.repository.fetch('examples/not_a_file.json'))
        self.assertEqual(len(self.repository.graph.facts), 0)

    def test_fetch(self):
        pathname = 'examples/miserables.json'
        self.assertTrue(os.path.isfile(pathname))
        self.repository.fetch(pathname)
        self.assertEqual(len(self.repository.graph.facts), 10)

    def test_facts(self):
        pathname = 'examples/miserables.json'
        self.assertTrue(os.path.isfile(pathname))
        self.repository.fetch(pathname)
        self.assertEqual(len(self.repository.graph.facts), 10)
        result = self.repository.graph.facts.matching((None, 'filename', None))
        _, _, filename = list(result)[0]
        self.assertEqual(filename, 'miserables.json')


class TestLocalRepositorySetup(unittest.TestCase):

    def test_init(self):
        with tempfile.TemporaryDirectory() as working_directory:
            path = os.path.join(working_directory, '.gitdata')
            self.assertFalse(os.path.exists(path))
            gitdata.repositories.create_respository(working_directory)
            repository = gitdata.repositories.Repository(working_directory)
            try:
                self.assertTrue(os.path.isfile(path))
            finally:
                del repository

    def test_init_repository_is_idempotent(self):
        with tempfile.TemporaryDirectory() as working_directory:
            path = os.path.join(working_directory, '.gitdata')
            repository_path, created = gitdata.repositories.init_repository(working_directory)
            self.assertTrue(created)
            self.assertEqual(repository_path, path)
            self.assertTrue(os.path.exists(path))

            repository_path, created = gitdata.repositories.init_repository(working_directory)
            self.assertFalse(created)
            self.assertEqual(repository_path, path)

    def test_init_repository_from_file_path(self):
        with tempfile.TemporaryDirectory() as working_directory:
            path = os.path.join(working_directory, '.gitdata')
            repository_path, created = gitdata.repositories.init_repository(path)
            self.assertTrue(created)
            self.assertEqual(repository_path, path)
            self.assertTrue(os.path.isfile(path))


class TestLocalRepository(RepositorySuite, unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.working_directory = self._tmpdir.name
        gitdata.repositories.create_respository(self.working_directory)
        self.repository = gitdata.repositories.Repository(self.working_directory)

    def tearDown(self):
        del self.repository
        self._tmpdir.cleanup()


class TestMemoryRepository(RepositorySuite, unittest.TestCase):

    def setUp(self):
        self.repository = gitdata.repositories.Repository()
        self.repository.graph.clear()
