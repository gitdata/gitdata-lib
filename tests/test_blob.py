"""
    test blob
"""

import unittest

from gitdata.connectors.common import Blob

class TestBlob(unittest.TestCase):

    def test_len(self):
        blob = Blob()
        blob.write(b'test')
        self.assertEqual(len(blob), 4)

    def test_str(self):
        blob = Blob()
        blob.write(b'test')
        self.assertEqual(str(blob), '4 bytes')

    def test_initial_len(self):
        blob = Blob()
        self.assertEqual(len(blob), 0)

    def test_initial_str(self):
        blob = Blob()
        self.assertEqual(str(blob), '0 bytes')

    def test_multiple_writes(self):
        blob = Blob()
        blob.write(b'first')
        self.assertEqual(len(blob), 5)  # 'first' is 5 bytes
        blob.write(b'second')
        self.assertEqual(len(blob), 11)  # 'first' + 'second' is 11 bytes
        self.assertEqual(str(blob), '11 bytes')

    def test_len_after_truncate(self):
        blob = Blob()
        blob.write(b'test')
        blob.truncate(2)
        self.assertEqual(len(blob), 2)
        self.assertEqual(str(blob), '2 bytes')