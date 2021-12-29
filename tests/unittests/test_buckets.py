"""
    test buckets
"""

import io
import tempfile
import unittest

import gitdata
from gitdata.buckets import Bucket, MemoryBucket


class TestFileBucket(unittest.TestCase):
    """test file buckets module"""

    def clear(self):
        bucket = Bucket(self.path, self.ids.pop)
        for item_id in bucket.keys():
            bucket.delete(item_id)

    def setUp(self):
        self.path = tempfile.TemporaryDirectory().name
        self.ids = ['id_%04d' % (9-i) for i in range(10)]
        self.clear()

    def tearDown(self):
        self.clear()

    def test_put_get(self):
        bucket = Bucket(self.path, self.ids.pop)
        item_id = bucket.put(b'some data')
        self.assertEqual(item_id, 'id_0000')
        self.assertEqual(bucket.get(item_id), b'some data')

    def test_item_exists(self):
        bucket = Bucket(self.path, self.ids.pop)
        item_id = bucket.put(b'some data')
        self.assertEqual(item_id, 'id_0000')
        self.assertEqual(bucket.exists(item_id), True)

    def test_keys(self):
        bucket = Bucket(self.path, self.ids.pop)
        self.assertEqual(bucket.put(b'some data'), 'id_0000')
        self.assertEqual(bucket.put(b'some more data'), 'id_0001')
        self.assertEqual(
            sorted(bucket.keys()),
            ['id_0000', 'id_0001']
        )

    def test_delete(self):
        bucket = Bucket(self.path, self.ids.pop)
        self.assertEqual(bucket.put(b'some data'), 'id_0000')
        self.assertEqual(bucket.put(b'some more data'), 'id_0001')
        self.assertEqual(
            sorted(bucket.keys()),
            ['id_0000', 'id_0001']
        )
        for item_id in bucket.keys():
            bucket.delete(item_id)
        self.assertEqual(
            sorted(bucket.keys()),
            []
        )


class TestMemoryBucket(unittest.TestCase):
    """test file buckets module"""

    def clear(self):
        bucket = self.bucket
        for item_id in bucket.keys():
            bucket.delete(item_id)

    def setUp(self):
        self.ids = ['id_%04d' % (9-i) for i in range(10)]
        self.bucket = MemoryBucket(self.ids.pop)

    def tearDown(self):
        self.clear()

    def test_put_get(self):
        bucket = self.bucket
        item_id = bucket.put(io.BytesIO(b'some data'))
        self.assertEqual(item_id, 'id_0000')
        self.assertEqual(bucket.get(item_id).read(), b'some data')

    def test_item_exists(self):
        bucket = self.bucket
        item_id = bucket.put(io.BytesIO(b'some data'))
        self.assertEqual(item_id, 'id_0000')
        self.assertEqual(bucket.exists(item_id), True)

    def test_keys(self):
        bucket = self.bucket
        self.assertEqual(bucket.put(io.BytesIO(b'some data')), 'id_0000')
        self.assertEqual(bucket.put(io.BytesIO(b'some more data')), 'id_0001')
        self.assertEqual(
            sorted(bucket.keys()),
            ['id_0000', 'id_0001']
        )

    def test_delete(self):
        bucket = self.bucket
        self.assertEqual(bucket.put(io.BytesIO(b'some data')), 'id_0000')
        self.assertEqual(bucket.put(io.BytesIO(b'some more data')), 'id_0001')
        self.assertEqual(
            sorted(bucket.keys()),
            ['id_0000', 'id_0001']
        )
        for item_id in bucket.keys():
            bucket.delete(item_id)
        self.assertEqual(
            sorted(bucket.keys()),
            []
        )
