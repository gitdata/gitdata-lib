"""
    graph tests
"""
# pylint: disable=missing-docstring, no-member

import datetime
from decimal import Decimal
import io

import unittest

from gitdata.graphs import Graph
from gitdata.utils import test_uid_maker

data = [
    dict(
        users=[
            dict(
                kind='user',
                name='Joe',
                birthdate=datetime.date(1991, 1, 2)
            ),
            dict(
                kind='user',
                name='Sally',
                birthdate=datetime.date(1991, 1, 2),
            ),
        ]
    ),
    dict(
        projects=[
            dict(
                kind='project',
                name='Project One',
                created=datetime.datetime(2019, 5, 2)
            ),
            dict(
                kind='project',
                name='Project Two',
                created=datetime.datetime(2019, 5, 3)
            ),
        ]
    ),
]


class GraphTests(unittest.TestCase):
    """Graph Tests"""

    def setUp(self):
        self.graph = Graph(new_uid=test_uid_maker())
        self.graph.clear()

    def tearDown(self):
        self.graph.clear()

    def test_empty_graph(self):
        g = self.graph
        self.assertEqual(g.facts.matching((None, None, None)), [])

    def test_add(self):
        g = self.graph
        g.add([dict(name='Joe', age=20), dict(name='Pat', wage=Decimal('12.1'))])
        person = g.get('3')
        self.assertEqual(person['wage'], Decimal('12.1'))
        self.assertEqual(person['name'], 'Pat')

    def test_stream_attribute(self):
        g = self.graph
        g.add([
            dict(name='Joe', age=20, image=io.BytesIO(b'image')),
            dict(name='Pat', wage=Decimal('12.1'))
        ])
        self.assertEqual(
            g.get('2')['image'].read(),
            b'image'
        )

    def test_query(self):
        g = self.graph
        g.add(data)
        result = g.query([
            (None, 'name', '?name')
        ])
        self.assertEqual(len(result), 4)

    def test_find(self):
        g = self.graph
        g.add(data)
        result = g.find('name')
        self.assertEqual(len(result), 4)

    def test_first(self):
        g = self.graph
        g.add(data)
        result = g.first('name')
        self.assertEqual(result['birthdate'], datetime.date(1991, 1, 2))

    def test_add_none(self):
        g = self.graph
        g.add(None)
        self.assertEqual(len(g), 0)

    def test_add_value(self):
        g = self.graph
        g.add('test')
        self.assertEqual(len(g), 0)

    def test_add_dict(self):
        g = self.graph
        g.add(dict(value=2))
        self.assertEqual(g.facts.matching(), [('1', 'value', 2)])

    def test_add_list(self):
        g = self.graph
        g.add([1, 2, 3])
        self.assertEqual(g.facts.matching((None, None, None)), [
            ('1', 'includes', 1),
            ('1', 'includes', 2),
            ('1', 'includes', 3)
        ])

    def test_add_project(self):
        g = self.graph
        project_attributes = dict(
            name='Sample',
            kind='project',
            created=datetime.datetime(2019, 6, 10),
            created_by=1,
        )
        g.add(project_attributes)
        self.assertEqual(g.facts.matching(), [
            ('1', 'name', 'Sample'),
            ('1', 'kind', 'project'),
            ('1', 'created', datetime.datetime(2019, 6, 10)),
            ('1', 'created_by', 1)
        ])

    def test_add_multiple(self):
        g = self.graph
        g.add(dict(data='123'))
        g.add(dict(data='234'))
        self.assertEqual(g.facts.matching(), [('1', 'data', '123'), ('2', 'data', '234')])

    def test_convert_to_dict(self):
        g = self.graph
        joe = dict(name='Joe', age=20)
        sam = dict(name='Sam', age=80)
        g.add(joe)
        g.add(sam)
        node = g.first(name='Joe')
        self.assertEqual(dict(node), joe)

    # def test_add_project_attribute(self):
    #     g = self.graph
    #     project_attributes = dict(
    #         name='Sample',
    #         kind='project',
    #         created=datetime.datetime(2019, 6, 10),
    #         created_by=1,
    #     )
    #     g.add(project_attributes)
    #     node = g.first(name='Sample')
    #     self.assertEqual(node['kind'], 'project')

    #     node.add('status', 'draft')
    #     self.assertEqual(g.facts.matching(), [
    #         ('1', 'name', 'Sample'),
    #         ('1', 'kind', 'project'),
    #         ('1', 'created', datetime.datetime(2019, 6, 10)),
    #         ('1', 'created_by', 1),
    #         ('1', 'status', 'draft'),
    #     ])

    # def test_add_project_attribute_as_list(self):
    #     g = self.graph
    #     project_attributes = dict(
    #         name='Sample',
    #         kind='project',
    #         created=datetime.datetime(2019, 6, 10),
    #         created_by=1,
    #     )
    #     g.add(project_attributes)
    #     node = g.first(name='Sample')

    #     node.add('cities', ['Vancouver', 'Victoria'])
    #     self.assertEqual(g.matching(), [
    #         ('1', 'name', 'Sample'),
    #         ('1', 'kind', 'project'),
    #         ('1', 'created', datetime.datetime(2019, 6, 10)),
    #         ('1', 'created_by', 1),
    #         ('2', 'includes', 'Vancouver'),
    #         ('2', 'includes', 'Victoria'),
    #         ('1', 'cities', '2'),
    #     ])

    # def test_add_project_attribute_as_list_of_objects(self):
    #     g = self.graph
    #     project_attributes = dict(
    #         name='Sample',
    #         kind='project',
    #         created=datetime.datetime(2019, 6, 10),
    #         created_by=1,
    #     )
    #     g.add(project_attributes)
    #     node = g.first(name='Sample')

    #     uid = g.add([
    #         dict(name='Vancouver'),
    #         dict(name='Victoria'),
    #     ])

    #     attribute = (node.uid, 'cities', uid)
    #     g.store.add([attribute])
    #     self.assertEqual(g.matching(), [
    #         ('1', 'name', 'Sample'),
    #         ('1', 'kind', 'project'),
    #         ('1', 'created', datetime.datetime(2019, 6, 10)),
    #         ('1', 'created_by', 1),
    #         ('3', 'name', 'Vancouver'),
    #         ('2', 'includes', '3'),
    #         ('4', 'name', 'Victoria'),
    #         ('2', 'includes', '4'),
    #         ('1', 'cities', '2'),
    #     ])

    # def test_add_list_of_objects_to_node(self):
    #     g = self.graph
    #     project_attributes = dict(
    #         name='Sample',
    #         kind='project',
    #         created=datetime.datetime(2019, 6, 10),
    #         created_by=1,
    #     )
    #     g.add(project_attributes)
    #     node = g.first(name='Sample')

    #     node.add('cities', [
    #         dict(name='Vancouver'),
    #         dict(name='Victoria'),
    #     ])

    #     self.assertEqual(g.matching(), [
    #         ('1', 'name', 'Sample'),
    #         ('1', 'kind', 'project'),
    #         ('1', 'created', datetime.datetime(2019, 6, 10)),
    #         ('1', 'created_by', 1),
    #         ('3', 'name', 'Vancouver'),
    #         ('2', 'includes', '3'),
    #         ('4', 'name', 'Victoria'),
    #         ('2', 'includes', '4'),
    #         ('1', 'cities', '2'),
    #     ])




class GraphTestsPreloaded(unittest.TestCase):
    """Graph Tests with Preloaded Data"""

    def setUp(self):
        self.graph = Graph(new_uid=test_uid_maker())
        # self.graph = gitdata.Graph(store, new_uid=new_test_uid(0))
        self.graph.clear()
        self.graph.add(data)

    def test_get(self):
        n4 = self.graph.get('4')
        self.assertEqual(dict(n4), dict(
            name='Joe',
            kind='user',
            birthdate=datetime.date(1991, 1, 2)
            )
        )

    def test_getitem(self):
        user = self.graph.get('4')
        self.assertEqual(user['name'], 'Joe')

    def test_first_again(self):
        project = dict(
            kind='project',
            name='Project One',
            created=datetime.datetime(2019, 5, 2)
        )
        project1 = self.graph.first(kind='project')
        self.assertEqual(project1, project)

    def test_len(self):
        self.assertEqual(len(self.graph), 20)

    def test_delete(self):
        g = self.graph

        self.assertEqual(g.query([
            ('?uid', 'name', '?name'),
            ('?uid', 'kind', 'user'),
        ]), [
            {'uid': '4', 'name': 'Joe'},
            {'uid': '5', 'name': 'Sally'}
        ])

        g.delete((None, 'name', 'Joe'))

        self.assertEqual(g.query([
            ('?uid', 'name', '?name'),
            ('?uid', 'kind', 'user'),
        ]), [
            {'uid': '5', 'name': 'Sally'}
        ])

    def test_first_missing(self):
        answer = self.graph.first(kind='animal')
        self.assertEqual(answer, None)

    def test_first(self):
        project1 = self.graph.first(kind='project')
        self.assertEqual(project1['name'], 'Project One')

    def test_exists(self):
        g = self.graph
        self.assertFalse(g.exists(kind='animal'))
        self.assertTrue(g.exists(kind='project'))
        g.delete((None, 'kind', 'project'))
        self.assertFalse(g.exists(kind='project'))

    def test_query(self):
        g = self.graph
        answer = g.query([
            ('?uid', 'name', '?name'),
            ('?uid', 'kind', 'user'),
        ])
        self.assertEqual(answer, [
            {'uid': '4', 'name': 'Joe'},
            {'uid': '5', 'name': 'Sally'}
        ])

    def test_find(self):
        g = self.graph
        answer = g.find(kind='project')
        self.assertEqual(len(answer), 2)
        self.assertEqual(answer[1]['name'], 'Project Two')

    def test_find_missing(self):
        g = self.graph
        answer = g.find(kind='animal')
        self.assertEqual(answer, [])

    # def test_iter_node_list(self):
    #     users = self.graph.get('2')
    #     print(users)
    #     names = [user.name for user in users]
    #     self.assertEqual(names, ['Joe', 'Sally'])

    # def test_traversal(self):
    #     Node = gitdata.Node
    #     g = self.graph
    #     print(g)
    #     print(g.first(name='Joe'))
    #     n = Node(graph=self.graph, uid='4')
    #     print(n)
    #     print(g.get('1'))
    #     self.assertEqual(
    #         n.projects, None
    #     )


