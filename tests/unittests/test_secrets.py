"""Secrets tests."""

import os
import tempfile
import unittest
from unittest.mock import patch

from gitdata.secrets import (
    DEFAULT_ENCRYPTION_KEY_NAME,
    ENCRYPTION_KEY_ENV_VAR,
    Secret,
    SecretsKeyMissingException,
    get_encryption_key,
    get_secrets,
)


class SecretsTests(unittest.TestCase):
    key = b'UJiNPZngqI2cj7CUQMuYHQQYE7p0bL7VYzfOT2saq2o='

    def test_set_and_get_secret(self):
        secrets = get_secrets(self.key)
        encrypted = secrets.set('mysecret', 'my value')
        self.assertIsInstance(encrypted, bytes)
        self.assertEqual(secrets.get('mysecret'), 'my value')

    def test_keys_and_len(self):
        secrets = get_secrets(self.key)
        secrets.set('secret1', 'my value 1')
        secrets.set('secret2', 'my value 2')
        self.assertEqual(secrets.keys(), ['secret1', 'secret2'])
        self.assertEqual(len(secrets), 2)

    def test_list_returns_records(self):
        secrets = get_secrets(self.key)
        secrets.set('secret1', 'my value 1')
        records = secrets.list()
        self.assertEqual(len(records), 1)
        self.assertIsInstance(records[0], Secret)
        self.assertEqual(records[0].name, 'secret1')
        self.assertEqual(records[0].value, '****')

    def test_list_reveal_returns_decrypted_values(self):
        secrets = get_secrets(self.key)
        secrets.set('secret1', 'my value 1')
        records = secrets.list(reveal=True)
        self.assertEqual(records[0].value, 'my value 1')

    def test_delete_secret(self):
        secrets = get_secrets(self.key)
        secrets.set('secret1', 'my value 1')
        secrets.set('secret2', 'my value 2')
        secrets.delete('secret1')
        self.assertEqual(secrets.keys(), ['secret2'])

    def test_exists_get_or_set_and_update(self):
        secrets = get_secrets(self.key)
        self.assertFalse(secrets.exists('a'))
        self.assertEqual(secrets.get_or_set('a', 'one'), 'one')
        self.assertEqual(secrets.get_or_set('a', 'two'), 'one')
        updated = secrets.update('a', 'three')
        self.assertEqual(updated, 'three')
        self.assertEqual(secrets.get('a'), 'three')

    def test_update_missing_raises(self):
        secrets = get_secrets(self.key)
        with self.assertRaises(KeyError):
            secrets.update('missing', 'value')

    def test_rename_pop_and_clear(self):
        secrets = get_secrets(self.key)
        secrets.set('old', 'value')
        secrets.rename('old', 'new')
        self.assertIsNone(secrets.get('old'))
        self.assertEqual(secrets.get('new'), 'value')
        popped = secrets.pop('new')
        self.assertEqual(popped, 'value')
        self.assertIsNone(secrets.get('new'))

        secrets.set('x', '1')
        secrets.set('y', '2')
        secrets.clear()
        self.assertEqual(len(secrets), 0)

    def test_first_masks_by_default(self):
        secrets = get_secrets(self.key)
        secrets.set('one', 'value')
        self.assertEqual(secrets.first('one').value, '****')
        self.assertEqual(secrets.first('one', reveal=True).value, 'value')

    def test_rename_missing_raises(self):
        secrets = get_secrets(self.key)
        with self.assertRaises(KeyError):
            secrets.rename('missing', 'new')

    def test_get_encryption_key_from_env(self):
        key = self.key.decode('utf-8')
        with patch.dict(os.environ, {ENCRYPTION_KEY_ENV_VAR: key}, clear=False):
            self.assertEqual(get_encryption_key(), self.key)

    def test_get_encryption_key_from_file(self):
        key = self.key.decode('utf-8')
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, DEFAULT_ENCRYPTION_KEY_NAME)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(key)
            with patch.dict(os.environ, {ENCRYPTION_KEY_ENV_VAR: ''}, clear=False):
                self.assertEqual(get_encryption_key(secrets_path=tmpdir), self.key)

    def test_missing_key_raises(self):
        with patch.dict(os.environ, {ENCRYPTION_KEY_ENV_VAR: ''}, clear=False):
            with self.assertRaises(SecretsKeyMissingException):
                get_secrets(None, key_name='missing_encryption_key_name')
