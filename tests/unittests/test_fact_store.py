"""
    gitdata fact store tests
"""
# pylint: disable=missing-docstring, no-member

from decimal import Decimal
from datetime import datetime, date
import io
import tempfile
import unittest
import os.path

import gitdata.stores.facts
from gitdata.utils import test_uid_maker


class EntityStoreSuite:
    """Standard Entity Store Test Suite"""

    entities = [
        dict(name='Pat', score=5, rate=Decimal('5')),
        dict(name='Sam', score=7, rate=Decimal('1')),
        dict(name='Terry', score=2, rate=Decimal('2')),
    ]

    facts = [
        ('2', 'name', 'Joe'),
        ('2', 'age', 12),
        ('1', 'includes', '2'),
        ('3', 'name', 'Sally'),
        ('3', 'wage', 22.1),
        ('1', 'includes', '3'),
    ]

    def test_add(self):
        joe = self.store.get('2')
        self.assertEqual(joe, None)
        self.store.add(self.facts)
        joe = self.store.get('2')
        self.assertEqual(joe['name'], 'Joe')

    def test_add_includes_none(self):
        four = self.store.get('4')
        self.assertEqual(four, None)
        self.store.add([
            ('4', 'name', 'Four'),
            ('4', 'age', None)
        ])
        four = self.store.get('4')
        self.assertEqual(four['name'], 'Four')
        with self.assertRaises(KeyError):
            four['age']  # pylint: disable=pointless-statement

    def test_add_only_none(self):
        four = self.store.get('4')
        self.assertEqual(four, None)
        self.store.add([
            ('4', 'name', 'Four'),
        ])
        self.store.add([
            ('4', 'age', None)
        ])
        four = self.store.get('4')
        self.assertEqual(four['name'], 'Four')
        with self.assertRaises(KeyError):
            four['age']  # pylint: disable=pointless-statement

    def test_remove(self):
        joe = self.store.get('2')
        self.assertEqual(joe, None)
        self.store.add(self.facts)
        joe = self.store.get('2')
        self.assertEqual(joe['name'], 'Joe')
        self.store.remove([('2', 'name', 'Joe')])
        joe = self.store.get('2')
        self.assertEqual(joe.get('name'), None)

    def test_put(self):
        ids = []
        for entity in self.entities:
            ids.append(self.store.put(entity))

        self.assertEqual(
            self.store.get(ids[1]),
            dict(name='Sam', score=7, rate=Decimal('1'))
        )

    def test_delete(self):
        ids = []
        for fact in self.entities:
            ids.append(self.store.put(fact))

        self.store.delete(ids[1])

        self.assertEqual(
            self.store.get(ids[1]),
            None
        )

        self.assertEqual(
            self.store.get(ids[2]),
            {'name': 'Terry', 'score': 2, 'rate': Decimal('2')}
        )

    def test_clear(self):
        ids = []
        for fact in self.entities:
            ids.append(self.store.put(fact))

        self.store.clear()

        self.assertEqual(
            self.store.get(ids[1]),
            None
        )

        self.assertEqual(
            self.store.get(ids[2]),
            None
        )

    def test_store_text(self):
        new_id = self.store.put(dict(value='test'))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], 'test')

    def test_store_integer(self):
        value = 1
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], value)

    def test_store_decimal(self):
        value = Decimal('2.4')
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], value)

    def test_store_date(self):
        value = date(2021, 1, 1)
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], value)

    def test_store_datetime(self):
        value = datetime(2021, 1, 1, 12, 10, 1)
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], value)

    def test_store_float(self):
        value = 1.245
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], value)

    def test_store_bool(self):
        value = True
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], value)

    def test_store_bytes(self):
        value = b'test123'
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'], value)

    def test_store_stream(self):
        content = b'test123'
        value = io.BytesIO(content)
        new_id = self.store.put(dict(value=value))
        entity = self.store.get(new_id)
        self.assertEqual(entity['value'].read(), content)

    def test_supported_values(self):
        values = ['test', 1, Decimal('2.1')]
        for value in values:
            new_id = self.store.put(dict(value=value))
            entity = self.store.get(new_id)
            self.assertEqual(entity['value'], value)

    def test_spo(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching(('2', 'name', 'Joe'))),
            [('2', 'name', 'Joe')],
        )

    def test_spn(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching(('3', 'name', None))),
            [
                ('3', 'name', 'Sally')
            ],
        )

    def test_sno(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching(('2', None, 'Joe'))),
            [
                ('2', 'name', 'Joe')
            ],
        )

    def test_snn(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching(('3', None, None))),
            [
                ('3', 'name', 'Sally'),
                ('3', 'wage', 22.1),
            ],
        )

    def test_npo(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching((None, 'name', 'Sally'))),
            [
                ('3', 'name', 'Sally'),
            ],
        )

    def test_npn(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching((None, 'name', None))),
            [
                ('2', 'name', 'Joe'),
                ('3', 'name', 'Sally'),
            ],
        )

    def test_nno(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching((None, None, 12))),
            [
                ('2', 'age', 12),
            ],
        )

    def test_nnn(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(
            list(self.store.matching((None, None, None))),
            [
                ('2', 'name', 'Joe'),
                ('2', 'age', 12),
                ('1', 'includes', '2'),
                ('3', 'name', 'Sally'),
                ('3', 'wage', 22.1),
                ('1', 'includes', '3'),
            ],
        )

    def test_len(self):
        store = self.store
        store.add(self.facts)
        self.assertEqual(len(store), 6)

    def test_str(self):
        store = self.store
        self.assertEqual(str(self.store), '')

        store.add(self.facts)
        self.assertEqual(
            str(self.store),
            (
                "('2', 'name', 'Joe')\n"
                "('2', 'age', 12)\n"
                "('1', 'includes', '2')\n"
                "('3', 'name', 'Sally')\n"
                "('3', 'wage', 22.1)\n"
                "('1', 'includes', '3')"
            )
        )

    def test_repr(self):
        store = self.store
        store_name = self.store.__class__.__name__

        self.assertEqual(repr(self.store), '%s()' % store_name)

        store.add(self.facts)
        self.assertEqual(
            repr(self.store),
            "%s(('2', 'name', 'Joe'), ('2', 'age', 12),"
            " ('1', 'includes', '2'), ('3', 'name', 'Sally'),"
            " ('3', 'wage', 22.1), ('1', 'includes', '3'))" % store_name
        )


class Sqlite3FileFactStoreTests(EntityStoreSuite, unittest.TestCase):
    """Sqlite3 Fact Store Tests"""

    def setUp(self):
        # path = tempfile.TemporaryDirectory().name
        path = 'tmp'
        if not os.path.exists(path):
            os.mkdir(path)
        pathname = os.path.join(path, 'facts')
        self.store = gitdata.stores.facts.Sqlite3FactStore(pathname)
        self.store.setup()

    def tearDown(self):
        self.store.clear()
        self.store.connection.close()
        os.remove('tmp/facts')
        os.rmdir('tmp/blobs')


class Sqlite3MemoryFactStoreTests(EntityStoreSuite, unittest.TestCase):
    """Sqlite3 Fact Store Tests"""

    def setUp(self):
        self.store = gitdata.stores.facts.Sqlite3FactStore(':memory:', new_uid=test_uid_maker())
        self.store.setup()


class MemoryFactStoreTests(EntityStoreSuite, unittest.TestCase):
    """Memory Fact Store Tests"""

    def setUp(self):
        self.store = gitdata.stores.facts.MemoryFactStore()
        self.store.setup()

