"""Secrets tests."""

import os
import tempfile
import unittest
from unittest.mock import patch

import gitdata.database
import gitdata.repositories
from gitdata.encryption import generate_key
from gitdata.secrets import (
    DEFAULT_ENCRYPTION_KEY_NAME,
    ENCRYPTION_KEY_ENV_VAR,
    MissingSecrets,
    Secret,
    SecretsKeyMissingException,
    get_encryption_key,
    get_secrets,
    resolve_secrets,
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

    def test_entity_store_set_get_and_upsert(self):
        db = gitdata.database.setup_test_database()
        try:
            secrets = get_secrets(self.key, db=db)
            secrets.set('token', 'one')
            secrets.set('token', 'two')
            self.assertEqual(secrets.get('token'), 'two')
            self.assertEqual(secrets.keys(), ['token'])
            self.assertEqual(len(secrets), 1)
            records = secrets.list()
            self.assertEqual(records[0].name, 'token')
            self.assertEqual(records[0].value, '****')
            secrets.delete('token')
            self.assertIsNone(secrets.get('token'))
            self.assertEqual(len(secrets), 0)
        finally:
            db.close()

    def test_entity_store_persists_across_connections(self):
        handle = tempfile.NamedTemporaryFile(suffix='.gitdata', delete=False)
        path = handle.name
        handle.close()
        try:
            db = gitdata.database.connect(database=path)
            secrets = get_secrets(self.key, db=db)
            secrets.set('token', 'abc')
            db.close()

            db = gitdata.database.connect(database=path)
            secrets = get_secrets(self.key, db=db)
            self.assertEqual(secrets.get('token'), 'abc')
            db.close()
        finally:
            os.remove(path)

    def test_repository_secrets_persist(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path, created = gitdata.repositories.init_repository(tmpdir)
            self.assertTrue(created)
            repository = gitdata.repositories.Repository(path)
            secrets = repository.secrets(self.key)
            secrets.set('gitlab-token', 'secret-value')

            repository = gitdata.repositories.Repository(path)
            secrets = repository.secrets(self.key)
            self.assertEqual(secrets.get('gitlab-token'), 'secret-value')
        finally:
            gitdata.repositories.remove_respository(tmpdir)
            os.rmdir(tmpdir)

    def test_resolve_all_present(self):
        secrets = get_secrets(self.key)
        secrets.set('gitlab-token', 'token-value')
        secrets.set('db-password', 'pw-value')
        resolved = secrets.resolve(['gitlab-token', 'db-password'])
        self.assertEqual(resolved, {
            'gitlab-token': 'token-value',
            'db-password': 'pw-value',
        })
        self.assertEqual(
            resolve_secrets(['gitlab-token'], key=self.key, storage=secrets.storage),
            {'gitlab-token': 'token-value'},
        )

    def test_resolve_empty_names(self):
        secrets = get_secrets(self.key)
        self.assertEqual(secrets.resolve([]), {})

    def test_resolve_one_missing(self):
        secrets = get_secrets(self.key)
        secrets.set('gitlab-token', 'token-value')
        with self.assertRaises(MissingSecrets) as ctx:
            secrets.resolve(['gitlab-token', 'db-password'])
        self.assertEqual(ctx.exception.names, ['db-password'])
        self.assertIn('db-password', str(ctx.exception))
        self.assertNotIn('token-value', str(ctx.exception))

    def test_resolve_several_missing(self):
        secrets = get_secrets(self.key)
        secrets.set('keep', 'keep-value')
        with self.assertRaises(MissingSecrets) as ctx:
            secrets.resolve(['zeta', 'keep', 'alpha'])
        self.assertEqual(ctx.exception.names, ['alpha', 'zeta'])
        self.assertNotIn('keep-value', str(ctx.exception))

    def test_resolve_missing_key(self):
        with patch.dict(os.environ, {ENCRYPTION_KEY_ENV_VAR: ''}, clear=False):
            with self.assertRaises(SecretsKeyMissingException):
                resolve_secrets(['gitlab-token'], key=None, key_name='missing_encryption_key_name')

    def test_resolve_wrong_key_treated_as_missing(self):
        secrets = get_secrets(self.key)
        secrets.set('gitlab-token', 'token-value')
        other = get_secrets(generate_key(), storage=secrets.storage)
        with self.assertRaises(MissingSecrets) as ctx:
            other.resolve(['gitlab-token'])
        self.assertEqual(ctx.exception.names, ['gitlab-token'])
        self.assertNotIn('token-value', str(ctx.exception))
