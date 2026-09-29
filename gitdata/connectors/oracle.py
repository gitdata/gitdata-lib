"""Oracle connector for direct CLI inspection."""

from contextlib import contextmanager
import os
import sys
from urllib.parse import parse_qs, unquote, urlsplit

from gitdata.connectors.common import BaseConnector, ConnectorError


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
        return (
            isinstance(ref, str)
            and ref.partition(':')[0].lower() == 'oracle'
        )

    def _parts(self, ref):
        try:
            parts = urlsplit(ref)
        except ValueError:
            raise OracleRefError('Oracle ref is malformed') from None
        query = parse_qs(parts.query, keep_blank_values=True)
        unexpected = set(query) - {'password_env'}
        if unexpected:
            raise OracleRefError(
                'Unsupported Oracle ref option(s): {}'.format(
                    ', '.join(
                        self._safe_component(option)
                        for option in sorted(unexpected)
                    )
                )
            )
        raw_service_name = parts.path.lstrip('/')
        service_name = unquote(raw_service_name)
        if (
                not parts.username
                or not parts.hostname
                or not service_name
                or '/' in service_name):
            raise OracleRefError(
                'Oracle refs require a user, host, and service name'
            )
        try:
            port = parts.port or 1521
        except ValueError:
            raise OracleRefError('Oracle refs require a valid port') from None
        if parts.password is not None:
            raise OracleRefError(
                'Inline Oracle passwords are not supported; use password_env'
            )
        password = None
        password_env = query.get('password_env', ())
        if password_env and (
                len(password_env) != 1 or not password_env[0]):
            raise OracleRefError(
                'password_env must name exactly one environment variable'
            )
        if password_env:
            variable = password_env[0]
            try:
                password = os.environ[variable]
            except KeyError:
                raise OracleRefError(
                    'Oracle password environment variable {!r} is not set'
                    .format(variable)
                )
        config = {
            'host': parts.hostname,
            'port': port,
            'service_name': service_name,
            'user': unquote(parts.username),
            'password': password,
        }
        table = unquote(parts.fragment) if parts.fragment else None
        return config, table

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
        host = cls._safe_component(config['host'])
        service = cls._safe_component(config['service_name'])
        server = '{}:{}'.format(host, config['port'])
        address = '{}/{}'.format(server, service)
        network_errors = (
            'DPY-6000', 'DPY-6005', 'ORA-12170', 'ORA-12541',
            'ORA-12543', 'ORA-12545',
        )
        if full_code in network_errors:
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
                'password_env in the Oracle ref.'.format(config['user'])
            )
        elif full_code in ('ORA-12514', 'DPY-6001'):
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
            dsn = oracledb.makedsn(
                config['host'],
                config['port'],
                service_name=config['service_name'],
            )
            return oracledb.connect(
                user=config['user'],
                password=config['password'],
                dsn=dsn,
            )
        except oracledb.Error as error:
            raise cls._connection_error(config, error) from None
        except OSError:
            host = cls._safe_component(config['host'])
            service = cls._safe_component(config['service_name'])
            address = '{}:{}/{}'.format(host, config['port'], service)
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

    def _table(self, config, name, count_rows, resolved=False):
        connection = self._connect(config)
        try:
            with self._translate_errors(config):
                with connection.cursor() as cursor:
                    query = (
                        'select c.column_name, c.data_type, c.nullable, '
                        'c.data_default, c.identity_column, c.virtual_column, '
                        "case when exists (select 1 from user_constraints k "
                        'join user_cons_columns kc on kc.constraint_name = '
                        "k.constraint_name where k.constraint_type = 'P' and "
                        'k.table_name = c.table_name and kc.table_name = '
                        'c.table_name and kc.column_name = c.column_name) '
                        "then 'PRI' else '-' end, c.data_precision, "
                        'c.data_scale, c.char_length, c.char_used '
                        'from user_tab_columns c where '
                        'c.table_name = :table_name order by c.column_id'
                    )
                    candidates = (
                        (name,) if resolved else self._selector_candidates(name)
                    )
                    schema = ()
                    actual_name = name
                    for candidate in candidates:
                        cursor.execute(query, {'table_name': candidate})
                        schema = tuple(cursor.fetchall())
                        if schema:
                            actual_name = candidate
                            break
        finally:
            self._close(connection, config)

        if not schema:
            raise ConnectorError(
                'Oracle table {!r} was not found in service {!r}. Check the '
                'table name.'.format(name, config['service_name'])
            )

        columns = tuple(
            self._normalize_identifier(row[0]) for row in schema
        )
        quoted = self._quoted(actual_name)

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
        config, selected_table = self._parts(ref)
        if selected_table:
            return self._table(config, selected_table, count_rows)

        connection = self._connect(config)
        try:
            with self._translate_errors(config):
                with connection.cursor() as cursor:
                    cursor.execute(
                        'select table_name from user_tables order by table_name'
                    )
                    table_pairs = tuple(
                        (self._normalize_identifier(row[0]), row[0])
                        for row in cursor
                    )
        finally:
            self._close(connection, config)

        names = tuple(display for display, _ in table_pairs)

        def tables():
            for _, actual_name in table_pairs:
                yield self._table(
                    config, actual_name, count_rows, resolved=True
                )

        def table_summaries():
            stats_connection = self._connect(config)
            try:
                with self._translate_errors(config):
                    with stats_connection.cursor() as cursor:
                        cursor.execute(
                            'select t.table_name, count(c.column_name), '
                            't.num_rows, round(nvl(s.bytes, 0) / 1024 / 1024) '
                            'from user_tables t left join user_tab_columns c '
                            'on c.table_name = t.table_name left join '
                            '(select segment_name, sum(bytes) bytes from '
                            'user_segments where segment_type in '
                            "('TABLE', 'TABLE PARTITION') group by segment_name) s "
                            'on s.segment_name = t.table_name group by '
                            't.table_name, t.num_rows, s.bytes order by '
                            't.table_name'
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
            'name': config['service_name'],
            'table_names': names,
            'tables': tables(),
            'table_summaries': table_summaries(),
        }
