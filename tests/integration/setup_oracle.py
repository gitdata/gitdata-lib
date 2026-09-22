"""Wait for Oracle and provision the disposable integration-test user."""

import os
import re
import time


_IDENTIFIER = re.compile(r'^[A-Z][A-Z0-9_]{0,29}$')
_PASSWORD = re.compile(r'^[A-Za-z][A-Za-z0-9_]{7,29}$')


def _validate_identifier(value, label):
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError('unsafe Oracle {}: {!r}'.format(label, value))
    return value


def _validate_password(value):
    if not _PASSWORD.fullmatch(value):
        raise ValueError('unsafe Oracle test password format')
    return value


def provision_user(connection, username, password):
    """Recreate a test user with only the privileges the tests require."""
    username = _validate_identifier(username, 'username')
    password = _validate_password(password)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT property_value
            FROM database_properties
            WHERE property_name = 'DEFAULT_PERMANENT_TABLESPACE'
            """
        )
        tablespace = _validate_identifier(cursor.fetchone()[0], 'tablespace')

        cursor.execute(
            'SELECT COUNT(*) FROM all_users WHERE username = :username',
            {'username': username},
        )
        if cursor.fetchone()[0]:
            cursor.execute('DROP USER {} CASCADE'.format(username))

        cursor.execute(
            'CREATE USER {} IDENTIFIED BY {}'.format(username, password)
        )
        cursor.execute(
            'GRANT CREATE SESSION, CREATE TABLE TO {}'.format(username)
        )
        cursor.execute(
            'ALTER USER {} QUOTA UNLIMITED ON {}'.format(
                username, tablespace
            )
        )


def connect_when_ready(driver, timeout=300):
    """Connect as SYSTEM, retrying while the disposable service starts."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return driver.connect(
                host=os.environ.get('GITDATA_TEST_ORACLE_HOST', 'oracle'),
                port=int(os.environ.get('GITDATA_TEST_ORACLE_PORT', '1521')),
                service_name=os.environ.get(
                    'GITDATA_TEST_ORACLE_SERVICE_NAME', 'FREEPDB1'
                ),
                user='SYSTEM',
                password=os.environ['ORACLE_PWD'],
            )
        except driver.Error:
            if time.monotonic() >= deadline:
                raise
            time.sleep(5)


def main():
    """Provision the configured Oracle integration-test account."""
    import oracledb

    connection = connect_when_ready(oracledb)
    try:
        provision_user(
            connection,
            username=os.environ['GITDATA_TEST_ORACLE_USER'],
            password=os.environ['GITDATA_TEST_ORACLE_PASSWORD'],
        )
    finally:
        connection.close()
    print('Oracle integration-test user is ready')


if __name__ == '__main__':
    main()
