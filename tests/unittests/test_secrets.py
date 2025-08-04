"""
    secrets tests
"""

import unittest
from gitdata.secrets import get_secrets

class SecretsTests(unittest.TestCase):

    def test_set_and_get_secret(self):
        secrets = get_secrets()
        secrets.set('mysecret', 'my value')
        assert secrets.get('mysecret') == 'my value'

    def test_list_secrets(self):
        secrets = get_secrets()
        secrets.set('secret1', 'my value 1')
        secrets.set('secret2', 'my value 2')
        self.assertEqual(secrets.list(), ['secret1', 'secret2'])

    def test_len_secrets(self):
        secrets = get_secrets()
        secrets.set('secret1', 'my value 1')
        secrets.set('secret2', 'my value 2')
        assert len(secrets) == 2

    def test_delete_secret(self):
        secrets = get_secrets()
        secrets.set('secret1', 'my value 1')
        secrets.set('secret2', 'my value 2')
        assert len(secrets) == 2
        self.assertEqual(secrets.list(), ['secret1', 'secret2'])
        secrets.delete('secret1')
        self.assertEqual(secrets.list(), ['secret2'])
