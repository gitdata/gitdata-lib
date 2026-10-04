"""Unit tests for optional Oracle database support."""

import builtins
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, call, patch

from gitdata.database import connect
from gitdata.database.common import DatabaseException


class TestOracleOptionalDependency(unittest.TestCase):

    def tearDown(self):
        sys.modules.pop('gitdata.database.oracle', None)

    def test_missing_driver_has_install_instructions(self):
        original_import = builtins.__import__

        def import_without_oracledb(name, *args, **kwargs):
            if name == 'oracledb':
                raise ImportError("No module named 'oracledb'")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=import_without_oracledb):
            with self.assertRaises(ImportError) as raised:
                connect('oracle', user='test', password='secret')

        self.assertIn('gitdata-lib[oracle]', str(raised.exception))

    def test_sqlite_connection_does_not_import_oracledb(self):
        original_import = builtins.__import__

        def reject_oracledb(name, *args, **kwargs):
            if name == 'oracledb':
                raise AssertionError('oracledb was imported')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=reject_oracledb):
            database = connect('sqlite3')
            self.assertEqual(list(database('select 1')), [(1,)])
            database.close()

    def test_oracle_adapter_module_can_be_discovered_without_driver(self):
        original_import = builtins.__import__

        def reject_oracledb(name, *args, **kwargs):
            if name == 'oracledb':
                raise AssertionError('oracledb was imported during discovery')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=reject_oracledb):
            module = importlib.import_module('gitdata.database.oracle')

        self.assertTrue(hasattr(module, 'OracleDatabase'))

    def test_connect_uses_thin_driver_with_service_name(self):
        driver = types.ModuleType('oracledb')
        driver.init_oracle_client = Mock()
        driver.makedsn = Mock(return_value='db.example:1522/FREEPDB1')
        driver.connect = Mock(return_value=Mock())

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle',
                host='db.example',
                port=1522,
                service_name='FREEPDB1',
                user='app',
                password='secret',
            )
            database.connect()

        driver.init_oracle_client.assert_not_called()
        driver.makedsn.assert_called_once_with(
            'db.example', 1522, service_name='FREEPDB1'
        )
        driver.connect.assert_called_once_with(
            user='app', password='secret', dsn='db.example:1522/FREEPDB1'
        )

    def test_connection_uses_synchronized_connection_helper(self):
        driver = types.SimpleNamespace(
            makedsn=Mock(return_value='dsn'),
            connect=Mock(),
        )
        connection = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            module = importlib.import_module('gitdata.database.oracle')
            with patch.object(
                    module, 'connect_oracle', return_value=connection,
            ) as synchronized_connect:
                database = connect(
                    'oracle',
                    service_name='FREEPDB1',
                    user='app',
                    password='secret',
                )
                database.connect()

        synchronized_connect.assert_called_once_with(
            driver,
            False,
            user='app',
            password='secret',
            dsn='dsn',
        )
        driver.connect.assert_not_called()

    def test_connect_thick_inits_oracle_client_once(self):
        driver = types.ModuleType('oracledb')
        setattr(driver, 'is_thin_mode', Mock(side_effect=[True, False]))
        driver.init_oracle_client = Mock()
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock(return_value=Mock())

        with patch.dict(sys.modules, {'oracledb': driver}):
            connect(
                'oracle',
                thick=True,
                service_name='FREEPDB1',
                user='app',
                password='secret',
            )
            connect(
                'oracle',
                thick=True,
                service_name='FREEPDB1',
                user='app',
                password='secret',
            )

        driver.init_oracle_client.assert_called_once_with()

    def test_connect_thick_missing_instant_client_fails_clearly(self):
        driver = types.ModuleType('oracledb')
        error_type = type('Error', (Exception,), {})
        setattr(driver, 'Error', error_type)
        setattr(driver, 'is_thin_mode', Mock(return_value=True))
        setattr(
            driver,
            'init_oracle_client',
            Mock(side_effect=error_type('DPI-1047')),
        )
        driver.makedsn = Mock()
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            with self.assertRaises(DatabaseException) as raised:
                connect(
                    'oracle',
                    thick=True,
                    service_name='FREEPDB1',
                    user='app',
                    password='secret',
                )

        self.assertIn('Instant Client', str(raised.exception))
        self.assertNotIn('DPI-1047', str(raised.exception))
        driver.connect.assert_not_called()
        driver.makedsn.assert_not_called()

    def test_execute_many_translates_every_positional_row(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        command, parameters = database.translate(
            'insert into things values (%s, %s)',
            (1, 'one'),
            (2, 'two'),
            many=True,
        )

        self.assertEqual(command, 'insert into things values (:1, :2)')
        self.assertEqual(parameters, [(1, 'one'), (2, 'two')])

    def test_execute_many_translates_every_named_row(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        command, parameters = database.translate(
            'insert into things values (%(id)s, %(name)s)',
            {'id': 1, 'name': 'one'},
            {'id': 2, 'name': 'two'},
            many=True,
        )

        self.assertEqual(command, 'insert into things values (:id, :name)')
        self.assertEqual(
            parameters,
            [{'id': 1, 'name': 'one'}, {'id': 2, 'name': 'two'}],
        )

    def test_table_names_are_normalized_for_unquoted_identifiers(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        with patch.object(
                type(database), 'execute', return_value=[('FIRST_TABLE',), ('SECOND_TABLE',)]):
            self.assertEqual(
                database.get_table_names(), ['first_table', 'second_table']
            )

    def test_quoted_metadata_identifier_case_is_preserved(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        metadata_rows = [
            ('ORDINARY_NAME',), ('MixedCaseName',), ('lowercase_name',)
        ]
        with patch.object(
                type(database), 'execute', return_value=metadata_rows):
            self.assertEqual(
                database.get_table_names(),
                ['ordinary_name', 'MixedCaseName', 'lowercase_name'],
            )
            self.assertEqual(
                database.get_schema_names(),
                ['ordinary_name', 'MixedCaseName', 'lowercase_name'],
            )
            self.assertEqual(
                database.get_database_names(),
                ['ordinary_name', 'MixedCaseName', 'lowercase_name'],
            )

    def test_column_names_use_a_bound_table_name(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        with patch.object(
                type(database), 'execute',
                side_effect=[[], [('ID',), ('DISPLAY_NAME',)]]) as execute:
            self.assertEqual(
                database.get_column_names('people'), ('id', 'display_name')
            )

        command = execute.call_args_list[0].args[0]
        self.assertIn('WHERE table_name = %s', command)
        self.assertEqual(
            execute.call_args_list,
            [call(command, 'people'), call(command, 'PEOPLE')],
        )

    def test_column_names_accept_exact_quoted_metadata_name(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        with patch.object(
                type(database), 'execute',
                return_value=[('ORDINARY_COLUMN',), ('MixedColumn',),
                              ('lowercase_column',)]) as execute:
            self.assertEqual(
                database.get_column_names('MixedTable'),
                ('ordinary_column', 'MixedColumn', 'lowercase_column'),
            )

        command, table_name = execute.call_args.args
        self.assertIn('WHERE table_name = %s', command)
        self.assertEqual(table_name, 'MixedTable')

    def test_schema_names_are_normalized(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        with patch.object(
                type(database), 'execute', return_value=[('APP',), ('SYSTEM',)]):
            self.assertEqual(database.get_schema_names(), ['app', 'system'])

    def test_database_names_reports_the_current_oracle_service(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', service_name='FREEPDB1', user='app', password='secret'
            )

        with patch.object(
                type(database), 'execute', return_value=[('FREEPDB1',)]):
            self.assertEqual(database.get_database_names(), ['freepdb1'])

    def test_use_builds_a_connection_for_another_service(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(side_effect=['free-dsn', 'other-dsn'])
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle',
                host='db.example',
                port=1521,
                service_name='FREEPDB1',
                user='app',
                password='secret',
            )
            other = database.use('OTHERPDB')

        self.assertEqual(other.get_kwargs()['dsn'], 'other-dsn')
        self.assertNotIn('db', other.get_kwargs())
        driver.makedsn.assert_called_with(
            'db.example', 1521, service_name='OTHERPDB'
        )

    def test_use_rejects_service_switching_for_an_explicit_dsn(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock()
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', dsn='custom-connect-descriptor', user='app',
                password='secret'
            )
            with self.assertRaisesRegex(ValueError, 'explicit dsn'):
                database.use('OTHERPDB')

        driver.makedsn.assert_not_called()

    def test_database_property_reports_oracle_connection_parameters(self):
        driver = types.ModuleType('oracledb')
        driver.makedsn = Mock(return_value='free-dsn')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle',
                host='db.example',
                port=1522,
                service_name='FREEPDB1',
                user='app',
                password='secret',
            )

        self.assertEqual(database.database.name, 'FREEPDB1')
        self.assertEqual(database.database.host, 'db.example')
        self.assertEqual(database.database.port, 1522)
        self.assertEqual(database.database.user, 'app')

    def test_database_property_for_dsn_does_not_fabricate_host_or_port(self):
        driver = types.ModuleType('oracledb')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', dsn='custom-connect-descriptor', user='app',
                password='secret'
            )

        self.assertEqual(database.database.name, 'custom-connect-descriptor')
        self.assertIsNone(database.database.host)
        self.assertIsNone(database.database.port)
        self.assertEqual(database.database.user, 'app')

    def test_database_property_prefers_explicit_dsn_over_service_details(self):
        driver = types.ModuleType('oracledb')
        driver.connect = Mock()

        with patch.dict(sys.modules, {'oracledb': driver}):
            database = connect(
                'oracle', dsn='custom-connect-descriptor',
                host='unused.example', port=1522, service_name='UNUSED_SERVICE',
                user='app', password='secret'
            )

        self.assertEqual(database.database.name, 'custom-connect-descriptor')
        self.assertIsNone(database.database.host)
        self.assertIsNone(database.database.port)
