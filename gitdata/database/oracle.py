"""Oracle Database support via the optional python-oracledb driver."""

from gitdata.oracle_client import (
    OracleClientError,
    connect_oracle,
    prepare_oracle_client,
)

from ..utils import Bunch
from .common import Database, DatabaseException


def _normalize_identifier(name):
    """Normalize ordinary Oracle identifiers without changing quoted case."""
    return name.lower() if name.isupper() else name


class OracleDatabase(Database):
    """Oracle Database connection backed by the python-oracledb driver."""

    paramstyle = 'named'
    connect_string_schema = 'oracle'

    def __init__(self, *args, **kwargs):
        import oracledb

        thick = kwargs.pop('thick', False)
        try:
            prepare_oracle_client(oracledb, thick)
        except OracleClientError as error:
            raise DatabaseException(str(error)) from None

        host = kwargs.pop('host', None)
        port = kwargs.pop('port', None)
        service_name = kwargs.pop('service_name', None)
        dsn = kwargs.get('dsn')

        self._uses_explicit_dsn = dsn is not None

        if dsn is None:
            if service_name is None:
                raise TypeError("Oracle connections require 'service_name' or 'dsn'")
            host = host or 'localhost'
            port = 1521 if port is None else port
            kwargs['dsn'] = oracledb.makedsn(
                host, port, service_name=service_name
            )

        self._host = None if self._uses_explicit_dsn else host
        self._port = None if self._uses_explicit_dsn else port
        self._service_name = (
            None if self._uses_explicit_dsn else service_name
        )

        self._dsn = kwargs['dsn']

        def connection_factory(*factory_args, **factory_kwargs):
            return connect_oracle(
                oracledb, thick, *factory_args, **factory_kwargs
            )

        Database.__init__(self, connection_factory, *args, **kwargs)

    def use(self, name):
        """Return a connection wrapper for another Oracle service."""
        if self._uses_explicit_dsn:
            raise ValueError("cannot switch services for an explicit dsn")
        kwargs = dict(self.get_kwargs())
        kwargs.pop('dsn', None)
        kwargs.update(
            host=self._host,
            port=self._port,
            service_name=name,
        )
        return type(self)(*self.get_args(), **kwargs)

    @property
    def database(self):
        """Return the public Oracle connection parameters."""
        return Bunch(
            name=self._dsn if self._uses_explicit_dsn else self._service_name,
            host=self._host,
            port=self._port,
            user=self.get_kwargs().get('user'),
        )

    def get_table_names(self):
        """Return tables owned by the connected Oracle user."""
        rows = self("SELECT table_name FROM user_tables ORDER BY table_name")
        return [_normalize_identifier(row[0]) for row in rows]

    def get_column_names(self, table_name):
        """Return columns for a table owned by the connected Oracle user."""
        command = """
        SELECT column_name
        FROM user_tab_columns
        WHERE table_name = %s
        ORDER BY column_id
        """
        rows = list(self(command, table_name))
        uppercase_name = table_name.upper()
        if not rows and uppercase_name != table_name:
            rows = self(command, uppercase_name)
        return tuple(_normalize_identifier(row[0]) for row in rows)

    def get_schema_names(self):
        """Return Oracle schemas visible to the connected user."""
        rows = self("SELECT username FROM all_users ORDER BY username")
        return [_normalize_identifier(row[0]) for row in rows]

    def get_database_names(self):
        """Return the current Oracle service name."""
        rows = self(
            "SELECT sys_context('USERENV', 'SERVICE_NAME') FROM dual"
        )
        return [_normalize_identifier(row[0]) for row in rows]
