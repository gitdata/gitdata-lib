"""
    gitdata digester tests
"""

import unittest

import gitdata.digester
from gitdata.utils import test_uid_maker

Digester = gitdata.digester.Digester


def digested(data):
    return gitdata.digester.digested(data, new_uid=test_uid_maker())


def undigested(data):
    return gitdata.digester.undigested(data)


class TestDigester(unittest.TestCase):

    def setUp(self):
        self.digester = Digester(new_uid=test_uid_maker())
        self.digester.known = []

    def test_dict(self):
        uid = self.digester.digest(dict(name='Joe', age=12))
        self.assertEqual(uid, '1')
        self.assertEqual(
            self.digester.known,
            [('1', 'name', 'Joe'), ('1', 'age', 12)],
        )

    def test_dict_u(self):
        facts = [('1', 'name', 'Joe'), ('1', 'age', 12)]
        self.assertEqual(
            undigested(facts),
            dict(name='Joe', age=12)
        )

    def test_list_of_dict(self):
        uid = self.digester.digest([dict(name='Joe', age=12), dict(name='Sally')])
        self.assertEqual(uid, '1')

        print(self.digester.known)
        self.assertEqual(
            self.digester.known,
            [
                ('2', 'name', 'Joe'),
                ('2', 'age', 12),
                ('1', 'includes', '2'),
                ('3', 'name', 'Sally'),
                ('1', 'includes', '3'),
            ],
        )

    def test_list_of_dict_u(self):
        data = [dict(name='Joe', age=12), dict(name='Sally')]
        facts = digested(data)
        self.assertEqual(undigested(facts), data)

    def test_single_value_ignored(self):
        data = self.digester.digest(10)
        self.assertEqual(data, 10)
        self.assertEqual(
            self.digester.known,
            [],
        )

    def test_list_of_values(self):
        uid = self.digester.digest(['one', 2, 'three'])
        self.assertEqual(uid, '1')
        self.assertEqual(
            self.digester.known,
            [
                ('1', 'includes', 'one'),
                ('1', 'includes', 2),
                ('1', 'includes', 'three')
            ],
        )

    def test_list_of_values_u(self):
        data = ['one', 2, 'three']
        facts = digested(data)
        self.assertEqual(undigested(facts), data)

    def test_dict_with_subdict(self):
        facts = digested(
            dict(name='Joe', age=12, friend=dict(name='Adam', age=12))
        )
        self.assertEqual(
            facts,
            [
                ('1', 'name', 'Joe'),
                ('1', 'age', 12),
                ('2', 'name', 'Adam'),
                ('2', 'age', 12),
                ('1', 'friend', '2')
            ]
        )

    def test_dict_with_subdict_u(self):
        data = dict(name='Joe', age=12, friend=dict(name='Adam', age=12))
        facts = digested(data)
        self.assertEqual(
            undigested(facts), data
        )

    def test_dict_with_list(self):
        facts = digested(
            dict(
                name='Joe',
                age=12,
                friend=[
                    dict(name='Adam', age=12),
                    dict(name='Jim', age=22),
                ]
            )
        )
        self.assertEqual(
            facts,
            [
                ('1', 'name', 'Joe'),
                ('1', 'age', 12),
                ('3', 'name', 'Adam'),
                ('3', 'age', 12),
                ('2', 'includes', '3'),
                ('4', 'name', 'Jim'),
                ('4', 'age', 22),
                ('2', 'includes', '4'),
                ('1', 'friend', '2')
            ]
        )

    def test_dict_with_list_u(self):
        data = dict(
            name='Joe',
            age=12,
            friend=[
                dict(name='Adam', age=12),
                dict(name='Jim', age=22),
            ]
        )
        facts = digested(data)
        self.assertEqual(undigested(facts), data)
