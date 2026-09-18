"""Secrets CLI tests."""

import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from docopt import docopt

import gitdata.repositories
from gitdata.cli import gitdata_secrets
from gitdata.encryption import generate_key
from gitdata.secrets import ENCRYPTION_KEY_ENV_VAR


class TestSecretsCli(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.tmpdir)
        gitdata.repositories.init_repository('.')
        self.key = generate_key().decode()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmpdir)

    def run_command(self, argv, stdin=None):
        args = docopt(gitdata_secrets.__doc__, argv=argv)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            if stdin is None:
                gitdata_secrets.secrets(args)
            else:
                with patch('sys.stdin', io.StringIO(stdin)):
                    gitdata_secrets.secrets(args)
        return stdout.getvalue()

    def test_keygen(self):
        output = self.run_command(['secrets', 'keygen']).strip()
        self.assertTrue(output)
        secrets = gitdata.repositories.Repository('.').secrets(output)
        secrets.set('x', 'y')
        self.assertEqual(secrets.get('x'), 'y')

    def test_set_get_list_delete(self):
        output = self.run_command(
            ['secrets', 'set', 'gitlab-token', 'secret-value', '--key', self.key]
        )
        self.assertEqual(output.strip(), 'secret set: gitlab-token')

        output = self.run_command(
            ['secrets', 'get', 'gitlab-token', '--key', self.key]
        )
        self.assertEqual(output.strip(), 'secret-value')

        output = self.run_command(['secrets', 'list', '--key', self.key])
        self.assertEqual(output.strip(), 'gitlab-token')

        output = self.run_command(
            ['secrets', 'ls', '--key', self.key]
        )
        self.assertEqual(output.strip(), 'gitlab-token')

        output = self.run_command(
            ['secrets', 'delete', 'gitlab-token', '--key', self.key]
        )
        self.assertEqual(output.strip(), 'secret deleted: gitlab-token')

        with self.assertRaises(SystemExit) as ctx:
            self.run_command(['secrets', 'get', 'gitlab-token', '--key', self.key])
        self.assertIn('secret not found', str(ctx.exception))

    def test_set_from_stdin(self):
        output = self.run_command(
            ['secrets', 'add', 'token', '-', '--key', self.key],
            stdin='from-stdin\n',
        )
        self.assertEqual(output.strip(), 'secret set: token')
        output = self.run_command(['secrets', 'get', 'token', '--key', self.key])
        self.assertEqual(output.strip(), 'from-stdin')

    def test_missing_repository(self):
        os.chdir(self.cwd)
        empty = tempfile.mkdtemp()
        try:
            os.chdir(empty)
            with self.assertRaises(SystemExit) as ctx:
                self.run_command(['secrets', 'list', '--key', self.key])
            self.assertIn('not a gitdata repository', str(ctx.exception))
        finally:
            os.chdir(self.cwd)
            shutil.rmtree(empty)

    def test_missing_key(self):
        env = os.environ.copy()
        env.pop(ENCRYPTION_KEY_ENV_VAR, None)
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                self.run_command(['secrets', 'list'])
            self.assertIn('encryption key missing', str(ctx.exception).lower())

    def test_key_file(self):
        key_path = os.path.join(self.tmpdir, 'key.txt')
        with open(key_path, 'w', encoding='utf-8') as handle:
            handle.write(self.key)
        self.run_command(
            ['secrets', 'set', 'a', 'b', '--key-file', key_path]
        )
        output = self.run_command(
            ['secrets', 'get', 'a', '--key-file', key_path]
        )
        self.assertEqual(output.strip(), 'b')

    def test_delete_unknown(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_command(['secrets', 'rm', 'missing', '--key', self.key])
        self.assertIn('unknown secret', str(ctx.exception))
