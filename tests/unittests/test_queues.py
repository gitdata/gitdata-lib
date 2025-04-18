"""
    test_queues.py

    Test the gitdata.queues module
"""

from decimal import Decimal
from datetime import date, datetime
import unittest

from gitdata.database import setup_test_database
from gitdata.queues import get_queues, queue_of


class TestStore(unittest.TestCase):

    def setUp(self):
        self.db = setup_test_database()
        self.queues = get_queues(db=self.db)
        self.messages =  queue_of('something', db=self.db)

    def tearDown(self):
        self.queues.clear()
        self.db.close()

    def test_put(self):
        messages = self.messages
        self.assertIsNone(messages.peek())
        self.assertEqual(messages.put(dict(message='Hello World!')), 1)
        self.assertEqual(len(messages), 1)

    def test_pop(self):
        messages = self.messages
        self.assertIsNone(messages.peek())
        self.assertEqual(messages.put(dict(message='Hello World!')), 1)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.pop(), dict(message='Hello World!'))
        self.assertEqual(len(messages), 0)

    def test_peek(self):
        messages = self.messages
        self.assertIsNone(messages.peek())
        self.assertEqual(messages.put(dict(message='Hello World!')), 1)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.peek(), dict(message='Hello World!'))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.peek(), dict(message='Hello World!'))
        self.assertEqual(len(messages), 1)
