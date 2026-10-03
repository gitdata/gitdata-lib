"""Oracle connector for direct CLI inspection."""

from contextlib import contextmanager
import sys
from urllib.parse import unquote, urlsplit

from gitdata.connectors.common import (
    BaseConnector,
    ConnectorError,
    password_from_environment,
)
from gitdata.oracle_client import OracleClientError, prepare_oracle_client

_SCHEME_TOKENS = frozenset({'sid', 'thick'})


class OracleRefError(ConnectorError, ValueError):
    """Raised when an Oracle ref cannot be used safely."""


class OracleConnector(BaseConnector):
    """Resolve Oracle URLs into directly inspectable roots."""

    @staticmethod
    def _normalize_identifier(name):
        if name.isupper():
            return name.lower()
        return '"{}"'.format(name.replace('"', '""'))

    @staticmethod
    def _data_type(schema_row):
        data_type = schema_row[1]
        if len(schema_row) <= 7:
            return data_type
        precision, scale, char_length, char_used = schema_row[7:11]
        if data_type == 'NUMBER' and precision is not None:
            if scale:
                return 'NUMBER({},{})'.format(precision, scale)
            return 'NUMBER({})'.format(precision)
        if char_length is not None and data_type in (
                'CHAR', 'NCHAR', 'NVARCHAR2', 'VARCHAR2'):
            semantics = ' CHAR' if char_used == 'C' else ''
            return '{}({}{})'.format(data_type, char_length, semantics)
        return data_type

    def accepts(self, ref):
        if not isinstance(ref, str):
            return False
        scheme = ref.partition(':')[0].lower()
        return scheme == 'oracle' or scheme.startswith('oracle+')

    def _parts(self, ref):
        try:
            parts = urlsplit(ref)
        except ValueError:
            raise OracleRefError('Oracle ref is malformed') from None
        if '?' in ref:
            raise OracleRefError(
                'Oracle refs do not accept query parameters'
            )
        if '#' in ref:
            raise OracleRefError(
                'Oracle refs do not accept fragment selectors; use '
                '/schema/table'
            )
        if not parts.username or not parts.hostname:
            raise OracleRefError('Oracle refs require a user and host')

        user = unquote(parts.username)
        tokens = parts.scheme.lower().split('+')
        if not tokens or tokens[0] != 'oracle':
            raise OracleRefError('Oracle refs require an oracle scheme')
        extras = tokens[1:]
        unknown = [token for token in extras if token not in _SCHEME_TOKENS]
        if unknown or len(extras) != len(set(extras)):
            raise OracleRefError(
                'Oracle ref scheme is not supported: {!r}'.format(parts.scheme)
            )
        sid_ref = 'sid' in extras
        thick = 'thick' in extras
        raw_path = parts.path.lstrip('/')
        raw_components = raw_path.split('/') if raw_path else []
        if len(raw_components) > 3 or not all(raw_components):
            path_error = (
                'Oracle SID refs accept a SID, schema, and optional table path'
                if sid_ref else
                'Oracle refs accept a service, schema, and optional table path'
            )
            raise OracleRefError(path_error)
        if sid_ref and not raw_components:
            raise OracleRefError(
                'Oracle SID refs require an explicit SID'
            )
        service_inferred = not raw_components
        connect_identifier = (
            user if service_inferred else unquote(raw_components[0])
        )
        schema = (
            unquote(raw_components[1]) if len(raw_components) >= 2 else None
        )
        table = (
            unquote(raw_components[2]) if len(raw_components) == 3 else None
        )
        if '/' in connect_identifier:
            identifier_kind = 'SID' if sid_ref else 'service'
            raise OracleRefError(
                'Oracle {} names containing slashes must be URL-encoded'
                .format(identifier_kind)
            )
        try:
            port = parts.port or 1521
        except ValueError:
            raise OracleRefError('Oracle refs require a valid port') from None
        if parts.password is not None:
            raise OracleRefError(
                'Inline Oracle passwords are not supported; set PASSWORD or '
                'name another variable with GITDATA_PASSWORD_ENV'
            )
        password = password_from_environment('Oracle', OracleRefError)
        connect_identifier_key = 'sid' if sid_ref else 'service_name'
        config = {
            'host': parts.hostname,
            'port': port,
            connect_identifier_key: connect_identifier,
            'user': user,
            'password': password,
            'thick': thick,
        }
        if service_inferred:
            config['_service_inferred'] = True
        return config, schema, table

    @staticmethod
    def _connect_identifier(config):
        if 'sid' in config:
            return 'sid', 'SID', config['sid']
        return 'service_name', 'service', config['service_name']

    @staticmethod
    def _safe_component(value):
        return str(value).encode('unicode_escape').decode('ascii')

    @classmethod
    def _error_code(cls, detail):
        full_code = getattr(detail, 'full_code', None)
        if full_code:
            return cls._safe_component(full_code)
        code = getattr(detail, 'code', None)
        if isinstance(code, int) and code > 0:
            return 'ORA-{:05d}'.format(code)
        return None

    @classmethod
    def _connection_error(cls, config, error):
        detail = error.args[0] if error.args else None
        full_code = cls._error_code(detail)
        detail_message = getattr(detail, 'message', '')
        identifier_key, _, identifier_value = cls._connect_identifier(config)
        sid_ref = identifier_key == 'sid'
        nested_identifier_code = 'DPY-6003:' if sid_ref else 'DPY-6001:'
        identifier_codes = (
            ('ORA-12505', 'DPY-6003') if sid_ref
            else ('ORA-12514', 'DPY-6001')
        )
        identifier_error = (
            full_code in identifier_codes
            or (
                isinstance(detail_message, str)
                and nested_identifier_code in detail_message
            )
        )
        identifier = cls._safe_component(identifier_value)
        host = cls._safe_component(config['host'])
        server = '{}:{}'.format(host, config['port'])
        address = '{}/{}'.format(server, identifier)
        network_errors = (
            'DPY-6000', 'DPY-6005', 'ORA-12170', 'ORA-12541',
            'ORA-12543', 'ORA-12545',
        )
        if full_code in network_errors and not identifier_error:
            message = (
                'could not connect to Oracle at {}. Check the server name, '
                'confirm the Oracle listener is running, and verify network '
                'access.'.format(address)
            )
        elif full_code == 'ORA-01017':
            message = (
                'could not authenticate Oracle user {!r} at {}. Check the '
                'user name and password.'.format(config['user'], address)
            )
        elif full_code in ('ORA-28000', 'ORA-28001'):
            message = (
                'Oracle account {!r} is locked or expired. Contact the '
                'database administrator.'.format(config['user'])
            )
        elif full_code == 'DPY-4001':
            message = (
                'Oracle credentials were not provided for user {!r}. Set '
                'PASSWORD or name another variable with '
                'GITDATA_PASSWORD_ENV.'.format(config['user'])
            )
        elif identifier_error:
            if sid_ref:
                message = (
                    'Oracle SID {!r} was not found at {}. Check the SID and '
                    'listener registration.'.format(identifier, server)
                )
            elif config.get('_service_inferred'):
                message = (
                    'Oracle service {!r}, inferred from user {!r}, was not '
                    'found at {}. Add an explicit service name to the ref.'
                    .format(
                        config['service_name'], config['user'], server
                    )
                )
            else:
                message = (
                    'Oracle service {!r} was not found at {}. Check the service '
                    'name and listener registration.'.format(
                        config['service_name'], server
                    )
                )
        else:
            code = cls._safe_component(full_code or 'unknown')
            message = (
                'Oracle operation failed at {} (error {}). Check the '
                'connection settings and access permissions.'.format(
                    address, code
                )
            )
        return ConnectorError(message)

    @classmethod
    @contextmanager
    def _translate_errors(cls, config):
        import oracledb

        try:
            yield
        except oracledb.Error as error:
            raise cls._connection_error(config, error) from None

    @classmethod
    def _close(cls, resource, config):
        """Close a driver resource without exposing driver exceptions."""
        import oracledb

        active_error = sys.exc_info()[0] is not None
        try:
            resource.close()
        except oracledb.Error as error:
            if not active_error:
                raise cls._connection_error(config, error) from None

    @classmethod
    def _connect(cls, config):
        try:
            import oracledb
        except ModuleNotFoundError as error:
            if error.name != 'oracledb':
                raise
            raise ConnectorError(
                'Oracle support requires the optional dependency; install it '
                "with 'pip install gitdata-lib[oracle]'."
            ) from None

        try:
            prepare_oracle_client(oracledb, config.get('thick'))
            identifier_key, _, identifier = cls._connect_identifier(config)
            dsn = oracledb.makedsn(
                config['host'],
                config['port'],
                **{identifier_key: identifier}
            )
            return oracledb.connect(
                user=config['user'],
                password=config['password'],
                dsn=dsn,
            )
        except OracleClientError as error:
            raise ConnectorError(str(error)) from None
        except oracledb.Error as error:
            raise cls._connection_error(config, error) from None
        except OSError:
            host = cls._safe_component(config['host'])
            _, _, identifier_value = cls._connect_identifier(config)
            identifier = cls._safe_component(identifier_value)
            address = '{}:{}/{}'.format(host, config['port'], identifier)
            raise ConnectorError(
                'could not connect to Oracle at {}. Check the server name, '
                'confirm the Oracle listener is running, and verify network '
                'access.'.format(address)
            ) from None

    @staticmethod
    def _quoted(name):
        return '"{}"'.format(name.replace('"', '""'))

    @staticmethod
    def _selector_candidates(name):
        if len(name) >= 2 and name.startswith('"') and name.endswith('"'):
            return (name[1:-1].replace('""', '"'),)
        if name.isupper():
            return (name,)
        return (name.upper(), name)

    def _table(
            self, config, owner, name, count_rows, resolved=False,
            owner_resolved=False):
        actual_owner = (
            owner if owner_resolved else self._selector_candidates(owner)[0]
        )
        connection = self._connect(config)
        try:
            with self._translate_errors(config):
                with connection.cursor() as cursor:
                    query = (
                        'select c.column_name, c.data_type, c.nullable, '
                        'c.data_default, c.identity_column, c.virtual_column, '
                        "case when exists (select 1 from all_constraints k "
                        'join all_cons_columns kc on kc.owner = k.owner and '
                        'kc.constraint_name = k.constraint_name where '
                        "k.constraint_type = 'P' and k.owner = c.owner and "
                        'k.table_name = c.table_name and kc.owner = c.owner '
                        'and kc.table_name = c.table_name and '
                        'kc.column_name = c.column_name) '
                        "then 'PRI' else '-' end, c.data_precision, "
                        'c.data_scale, c.char_length, c.char_used '
                        'from all_tab_cols c where c.owner = :owner and '
                        "c.user_generated = 'YES' and "
                        'c.table_name = :table_name order by c.column_id'
                    )
                    candidates = (
                        (name,) if resolved else self._selector_candidates(name)
                    )
                    schema = ()
                    actual_name = name
                    for candidate in candidates:
                        cursor.execute(
                            query,
                            {
                                'owner': actual_owner,
                                'table_name': candidate,
                            },
                        )
                        schema = tuple(cursor.fetchall())
                        if schema:
                            actual_name = candidate
                            break
        finally:
            self._close(connection, config)

        if not schema:
            raise ConnectorError(
                'Oracle table {!r} was not found in schema {!r}. Check the '
                'table name.'.format(name, owner)
            )

        columns = tuple(
            self._normalize_identifier(row[0]) for row in schema
        )
        quoted = '{}.{}'.format(
            self._quoted(actual_owner), self._quoted(actual_name)
        )

        def eager_count():
            count_connection = self._connect(config)
            try:
                with self._translate_errors(config):
                    with count_connection.cursor() as cursor:
                        cursor.execute('select count(*) from {}'.format(quoted))
                        return cursor.fetchone()[0]
            finally:
                self._close(count_connection, config)

        row_count = eager_count() if count_rows else None

        def rows():
            import oracledb

            lob_type = getattr(oracledb, 'LOB', ())
            row_connection = self._connect(config)
            cursor = None
            try:
                with self._translate_errors(config):
                    cursor = row_connection.cursor()
                    cursor.execute('select * from {}'.format(quoted))
                    for row in cursor:
                        yield tuple(
                            value.read(1, 4096)
                            if isinstance(value, lob_type) else value
                            for value in row
                        )
            finally:
                try:
                    if cursor is not None:
                        self._close(cursor, config)
                finally:
                    self._close(row_connection, config)

        def column_summaries():
            for row, column_name in zip(schema, columns):
                extra = []
                if row[4] == 'YES':
                    extra.append('IDENTITY')
                if row[5] == 'YES':
                    extra.append('VIRTUAL')
                yield {
                    'name': column_name,
                    'type': 'column',
                    'data_type': self._data_type(row),
                    'null': 'YES' if row[2] == 'Y' else 'NO',
                    'key': row[6] if len(row) > 6 else '-',
                    'default': (
                        row[3].strip()
                        if isinstance(row[3], str) and row[3].strip()
                        else '-'
                    ),
                    'extra': ', '.join(extra) or '-',
                }

        return {
            'type': 'table',
            'name': self._normalize_identifier(actual_name),
            'columns': columns,
            'row_count': row_count,
            'rows': rows(),
            'column_summaries': column_summaries(),
        }

    def fetch(self, ref, count_rows=True):
        if not self.accepts(ref):
            return None
        config, selected_schema, selected_table = self._parts(ref)
        if selected_table:
            return self._table(
                config, selected_schema, selected_table, count_rows
            )
        if selected_schema is None:
            connection = self._connect(config)
            try:
                with self._translate_errors(config):
                    with connection.cursor() as cursor:
                        cursor.execute(
                            'select distinct owner from all_tables order by owner'
                        )
                        names = tuple(
                            self._normalize_identifier(row[0]) for row in cursor
                        )
            finally:
                self._close(connection, config)
            _, _, connection_name = self._connect_identifier(config)

            def database_summaries():
                stats_connection = self._connect(config)
                try:
                    with self._translate_errors(config):
                        with stats_connection.cursor() as cursor:
                            cursor.execute(
                                'select owner, count(*), '
                                'case when count(num_rows) = count(*) '
                                'then sum(num_rows) end, '
                                'cast(null as number) from all_tables '
                                'group by owner order by owner'
                            )
                            for row in cursor:
                                yield {
                                    'name': self._normalize_identifier(row[0]),
                                    'type': 'database',
                                    'tables': int(row[1]),
                                    'rows': (
                                        int(row[2])
                                        if row[2] is not None else '-'
                                    ),
                                    'size': (
                                        int(row[3])
                                        if row[3] is not None else '-'
                                    ),
                                }
                finally:
                    self._close(stats_connection, config)

            return {
                'type': 'server',
                'name': connection_name,
                'item_label': 'Schema',
                'database_names': names,
                'database_summaries': database_summaries(),
            }

        actual_owner = self._selector_candidates(selected_schema)[0]
        connection = self._connect(config)
        try:
            with self._translate_errors(config):
                with connection.cursor() as cursor:
                    cursor.execute(
                        'select table_name from all_tables '
                        'where owner = :owner order by table_name',
                        {'owner': actual_owner},
                    )
                    table_pairs = tuple(
                        (self._normalize_identifier(row[0]), row[0])
                        for row in cursor
                    )
        finally:
            self._close(connection, config)

        if not table_pairs:
            raise ConnectorError(
                'Oracle schema {!r} has no tables visible to user {!r}. '
                'Check the schema name and access permissions.'.format(
                    self._safe_component(selected_schema),
                    self._safe_component(config['user']),
                )
            )

        names = tuple(display for display, _ in table_pairs)

        def tables():
            for _, actual_name in table_pairs:
                yield self._table(
                    config, actual_owner, actual_name, count_rows,
                    resolved=True, owner_resolved=True
                )

        def table_summaries():
            stats_connection = self._connect(config)
            try:
                with self._translate_errors(config):
                    with stats_connection.cursor() as cursor:
                        cursor.execute(
                            'select t.table_name, count(c.column_name), '
                            't.num_rows, cast(null as number) '
                            'from all_tables t left join all_tab_columns c '
                            'on c.owner = t.owner and '
                            'c.table_name = t.table_name '
                            'where t.owner = :owner group by '
                            't.table_name, t.num_rows order by '
                            't.table_name',
                            {'owner': actual_owner},
                        )
                        for row in cursor:
                            yield {
                                'name': self._normalize_identifier(row[0]),
                                'type': 'table',
                                'columns': int(row[1]),
                                'rows': (
                                    int(row[2]) if row[2] is not None else '-'
                                ),
                                'size': (
                                    int(row[3]) if row[3] is not None else '-'
                                ),
                            }
            finally:
                self._close(stats_connection, config)

        return {
            'type': 'database',
            'name': self._normalize_identifier(actual_owner),
            'table_names': names,
            'tables': tables(),
            'table_summaries': table_summaries(),
        }
