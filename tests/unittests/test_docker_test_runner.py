"""Tests for the sequential Docker test runner."""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / 'tests' / 'run_with_docker.sh'


class TestDockerTestRunner(unittest.TestCase):

    def _fake_docker(self, directory):
        docker = Path(directory) / 'docker'
        docker.write_text(
            '#!/usr/bin/env bash\n'
            'printf "%s\\n" "$*" >> "$FAKE_DOCKER_LOG"\n'
            'if [[ -n "${FAKE_DOCKER_FAIL_MATCH:-}" && '
            '"$*" == *"$FAKE_DOCKER_FAIL_MATCH"* ]]; then exit 1; fi\n'
            'if [[ "$1 $2" == "network create" ]]; then '
            'printf "%s\\n" "$3"; fi\n'
            'if [[ "$1" == "create" ]]; then '
            'previous=""; for argument in "$@"; do '
            'if [[ "$previous" == "--name" ]]; then '
            'printf "%s\\n" "$argument"; break; fi; '
            'previous="$argument"; done; fi\n'
            'if [[ "$1 $2" == "inspect --format" ]]; then '
            'printf "healthy\\n"; fi\n'
        )
        docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
        return docker

    def _run(self, fail_match=None, run_id='unit'):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'docker.log'
            self._fake_docker(directory)
            env = dict(os.environ)
            for name in (
                'DOCKER',
                'GITDATA_TEST_IMAGE',
                'GITDATA_TEST_MARIADB_IMAGE',
                'GITDATA_TEST_POSTGRES_IMAGE',
                'GITDATA_TEST_ORACLE_IMAGE',
            ):
                env.pop(name, None)
            env.update(
                PATH=directory + os.pathsep + env['PATH'],
                FAKE_DOCKER_LOG=str(log),
                GITDATA_TEST_RUN_ID=run_id,
            )
            if fail_match:
                env['FAKE_DOCKER_FAIL_MATCH'] = fail_match
            result = subprocess.run(
                ['bash', str(RUNNER)],
                cwd=str(ROOT),
                env=env,
                text=True,
                capture_output=True,
            )
            commands = log.read_text().splitlines() if log.exists() else []
            return result, commands

    def test_runs_database_services_sequentially(self):
        result, commands = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)
        command_log = '\n'.join(commands)
        self.assertIn('TestSqlite3Database', command_log)
        self.assertIn('TestMySQLDatabase', command_log)
        self.assertIn('TestPostgreSQLDatabase', command_log)
        self.assertIn('tests/integration/test_database_oracle.py', command_log)
        self.assertIn(
            'build -f {} -t gitdata-lib-tests:unit'.format(
                ROOT / 'tests' / 'Dockerfile'
            ),
            command_log,
        )
        self.assertIn('image rm gitdata-lib-tests:unit', command_log)

        maria_start = next(
            i for i, command in enumerate(commands)
            if 'create --name' in command and 'gitdata-test-unit-mariadb' in command
        )
        maria_stop = next(
            i for i, command in enumerate(commands)
            if 'rm -f gitdata-test-unit-mariadb' in command
        )
        postgres_start = next(
            i for i, command in enumerate(commands)
            if 'create --name' in command and 'gitdata-test-unit-postgres' in command
        )
        postgres_stop = next(
            i for i, command in enumerate(commands)
            if 'rm -f gitdata-test-unit-postgres' in command
        )
        oracle_start = next(
            i for i, command in enumerate(commands)
            if 'create --name' in command and 'gitdata-test-unit-oracle' in command
        )
        oracle_stop = next(
            i for i, command in enumerate(commands)
            if 'rm -f gitdata-test-unit-oracle' in command
        )

        self.assertLess(maria_start, maria_stop)
        self.assertLess(maria_stop, postgres_start)
        self.assertLess(postgres_start, postgres_stop)
        self.assertLess(postgres_stop, oracle_start)
        self.assertLess(oracle_start, oracle_stop)

    def test_cleans_up_the_active_service_after_failure(self):
        result, commands = self._run('TestMySQLDatabase')

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any(
            'rm -f gitdata-test-unit-mariadb' in command
            for command in commands
        ))
        self.assertTrue(any(
            'network rm gitdata-test-unit-mariadb' in command
            for command in commands
        ))
        self.assertFalse(any(
            'gitdata-test-unit-postgres' in command
            for command in commands
        ))

    def test_does_not_remove_a_preexisting_network_after_name_collision(self):
        result, commands = self._run('network create')

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('rm -f gitdata-test-unit-mariadb' in command
                             for command in commands))
        self.assertFalse(any('network rm gitdata-test-unit-mariadb' in command
                             for command in commands))

    def test_does_not_remove_a_preexisting_container_after_name_collision(self):
        result, commands = self._run('create --name')

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('rm -f gitdata-test-unit-mariadb' in command
                             for command in commands))
        self.assertTrue(any('network rm gitdata-test-unit-mariadb' in command
                            for command in commands))

    def test_removes_owned_container_if_start_fails(self):
        result, commands = self._run('start gitdata-test-unit-mariadb')

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any('rm -f gitdata-test-unit-mariadb' in command
                            for command in commands))
        self.assertTrue(any('network rm gitdata-test-unit-mariadb' in command
                            for command in commands))

    def test_rejects_an_empty_run_id(self):
        result, commands = self._run(run_id='')

        self.assertEqual(result.returncode, 2)
        self.assertIn('Invalid GITDATA_TEST_RUN_ID', result.stderr)
        self.assertEqual(commands, [])

    def test_docker_context_excludes_nested_secret_files(self):
        dockerignore = ROOT / '.dockerignore'
        if not dockerignore.exists():
            self.skipTest('.dockerignore is not copied into the test image')
        patterns = set(dockerignore.read_text().splitlines())

        self.assertIn('**/.gitdata', patterns)
        self.assertIn('**/*.pem', patterns)
        self.assertIn('**/*.key', patterns)
        self.assertIn('!tests/unittests/.gitdata', patterns)

    def test_retries_test_image_cleanup_failure(self):
        result, commands = self._run('image rm')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            'Failed to remove test image gitdata-lib-tests:unit',
            result.stderr,
        )
        self.assertEqual(
            sum('image rm gitdata-lib-tests:unit' in command
                for command in commands),
            2,
        )

    def test_fails_if_service_cleanup_fails(self):
        result, commands = self._run('network rm')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            'Failed to remove network gitdata-test-unit-mariadb',
            result.stderr,
        )
        self.assertEqual(
            sum('network rm gitdata-test-unit-mariadb' in command
                for command in commands),
            2,
        )
        self.assertFalse(any(
            'gitdata-test-unit-postgres' in command
            for command in commands
        ))


if __name__ == '__main__':
    unittest.main()
