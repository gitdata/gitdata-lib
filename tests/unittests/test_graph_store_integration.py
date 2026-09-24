"""Integration contract for Digester -> Graph -> FactStore."""

import os
from pathlib import Path
import tempfile
import unittest

from gitdata.digester import is_relationship, undigested
from gitdata.graphs import Graph
from gitdata.repositories import Repository, init_repository
from gitdata.utils import test_uid_maker


def inferred_roots(facts):
    """Infer roots as subjects which are not also referenced subjects."""
    subjects = []
    for subject, _, _ in facts:
        if subject not in subjects:
            subjects.append(subject)
    referenced_subjects = {
        value for _, predicate, value in facts
        if is_relationship(predicate)
    }
    return [subject for subject in subjects if subject not in referenced_subjects]


class RootInferenceTests(unittest.TestCase):

    def test_literal_equal_to_subject_does_not_create_parent_relationship(self):
        facts = [
            ('1', 'external_code', '2'),
            ('2', 'name', 'independent'),
        ]

        self.assertEqual(inferred_roots(facts), ['1', '2'])


class MemoryGraphStoreIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.graph = Graph(new_uid=test_uid_maker())
        self.graph.clear()

    def test_one_source_is_digested_into_retrievable_facts(self):
        self.graph.add({
            'name': 'source-one',
            'children': [
                {'name': 'alpha'},
                {'name': 'beta'},
            ],
        })

        self.assertEqual(list(self.graph.facts.matching()), [
            ('1', 'name', 'source-one'),
            ('3', 'name', 'alpha'),
            ('2', '.includes', '3'),
            ('4', 'name', 'beta'),
            ('2', '.includes', '4'),
            ('1', '.children', '2'),
        ])

    def test_multiple_sources_coexist_and_have_independent_inferred_roots(self):
        self.graph.add({
            'name': 'source-one',
            'children': [{'name': 'alpha'}],
        })
        self.graph.add({
            'name': 'source-two',
            'children': [{'name': 'beta'}],
        })

        facts = list(self.graph.facts.matching())
        roots = inferred_roots(facts)

        self.assertEqual(roots, ['1', '4'])
        root_names = [
            next(value for _, _, value in self.graph.facts.matching((root, 'name', None)))
            for root in roots
        ]
        self.assertEqual(root_names, ['source-one', 'source-two'])
        self.assertEqual(len(facts), 8)


class SqliteGraphStoreIntegrationTests(unittest.TestCase):

    def test_literal_equal_to_child_uid_survives_reopening_store(self):
        data = ['2', {'name': 'node'}]

        with tempfile.TemporaryDirectory() as tempdir:
            pathname = os.path.join(tempdir, '.gitdata')
            graph = Graph(pathname, new_uid=test_uid_maker())
            graph.setup()
            graph.add(data)
            getattr(graph.facts, 'connection').close()

            reopened = Graph(pathname)
            facts = list(reopened.facts.matching())

            self.assertEqual(inferred_roots(facts), ['1'])
            self.assertEqual(undigested(facts), data)
            getattr(reopened.facts, 'connection').close()

    def test_empty_values_are_omitted_after_reopening_store(self):
        data = {
            'name': 'source',
            'mapping': {},
            'sequence': [],
            'nested': [[], {}],
            'description': None,
        }

        with tempfile.TemporaryDirectory() as tempdir:
            pathname = os.path.join(tempdir, '.gitdata')
            graph = Graph(pathname, new_uid=test_uid_maker())
            graph.setup()
            graph.add(data)
            getattr(graph.facts, 'connection').close()

            reopened = Graph(pathname)
            facts = list(reopened.facts.matching())

            self.assertEqual(facts, [('1', 'name', 'source')])
            self.assertEqual(undigested(facts), {'name': 'source'})
            getattr(reopened.facts, 'connection').close()

    def test_multiple_sources_survive_closing_and_reopening_one_store(self):
        with tempfile.TemporaryDirectory() as tempdir:
            pathname = os.path.join(tempdir, '.gitdata')
            graph = Graph(pathname, new_uid=test_uid_maker())
            graph.setup()
            graph.add({
                'name': 'source-one',
                'children': [{'name': 'alpha'}],
            })
            graph.add({
                'name': 'source-two',
                'children': [{'name': 'beta'}],
            })
            getattr(graph.facts, 'connection').close()

            reopened = Graph(pathname)
            facts = list(reopened.facts.matching())
            roots = inferred_roots(facts)
            root_names = [
                next(value for _, _, value in reopened.facts.matching((root, 'name', None)))
                for root in roots
            ]

            self.assertEqual(root_names, ['source-one', 'source-two'])
            self.assertEqual(len(facts), 8)
            getattr(reopened.facts, 'connection').close()


class RepositoryMultipleSourcesTests(unittest.TestCase):

    def test_two_local_files_are_stored_as_two_fact_graphs_in_one_repository(self):
        with tempfile.TemporaryDirectory() as tempdir:
            first = Path(tempdir, 'first.txt')
            second = Path(tempdir, 'second.txt')
            first.write_text('first', encoding='utf-8')
            second.write_text('second', encoding='utf-8')
            repository_path, _ = init_repository(tempdir)

            repository = Repository(repository_path)
            repository.fetch(str(first))
            repository.fetch(str(second))
            facts = list(repository.graph.facts.matching())
            roots = inferred_roots(facts)
            filenames = [
                next(value for _, _, value in repository.graph.facts.matching(
                    (root, 'filename', None)
                ))
                for root in roots
            ]

            self.assertEqual(filenames, ['first.txt', 'second.txt'])
            self.assertEqual(len(roots), 2)
            getattr(repository.graph.facts, 'connection').close()

            reopened = Repository(repository_path)
            reopened_facts = list(reopened.graph.facts.matching())
            self.assertEqual(len(inferred_roots(reopened_facts)), 2)
            getattr(reopened.graph.facts, 'connection').close()


if __name__ == '__main__':
    unittest.main()
