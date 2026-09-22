"""Tests for Oracle integration-test provisioning."""

import unittest

from tests.integration import setup_oracle


class FakeCursor:

    def __init__(self, user_exists=False):
        self.user_exists = user_exists
        self.commands = []
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, command, parameters=None):
        self.commands.append((command, parameters))
        if 'database_properties' in command:
            self._result = ('SYSTEM',)
        elif 'all_users' in command:
            self._result = (1 if self.user_exists else 0,)

    def fetchone(self):
        return self._result


class FakeConnection:

    def __init__(self, user_exists=False):
        self.cursor_instance = FakeCursor(user_exists=user_exists)

    def cursor(self):
        return self.cursor_instance


class TestOracleTestSetup(unittest.TestCase):

    def test_provisions_user_with_quota_on_default_tablespace(self):
        connection = FakeConnection()

        setup_oracle.provision_user(
            connection,
            username='GITDATA_TEST',
            password='GitDataApp123',
        )

        commands = [command for command, _ in connection.cursor_instance.commands]
        self.assertIn(
            'CREATE USER GITDATA_TEST IDENTIFIED BY GitDataApp123',
            commands,
        )
        self.assertIn(
            'GRANT CREATE SESSION, CREATE TABLE TO GITDATA_TEST',
            commands,
        )
        self.assertIn(
            'ALTER USER GITDATA_TEST QUOTA UNLIMITED ON SYSTEM',
            commands,
        )
        self.assertNotIn(
            'GRANT UNLIMITED TABLESPACE TO GITDATA_TEST',
            commands,
        )

    def test_recreates_an_existing_test_user(self):
        connection = FakeConnection(user_exists=True)

        setup_oracle.provision_user(
            connection,
            username='GITDATA_TEST',
            password='GitDataApp123',
        )

        commands = [command for command, _ in connection.cursor_instance.commands]
        self.assertIn('DROP USER GITDATA_TEST CASCADE', commands)

    def test_rejects_unsafe_identifiers_and_passwords(self):
        connection = FakeConnection()

        with self.assertRaises(ValueError):
            setup_oracle.provision_user(
                connection,
                username='GITDATA_TEST; DROP USER SYSTEM',
                password='GitDataApp123',
            )
        with self.assertRaises(ValueError):
            setup_oracle.provision_user(
                connection,
                username='GITDATA_TEST',
                password='bad password',
            )


if __name__ == '__main__':
    unittest.main()
