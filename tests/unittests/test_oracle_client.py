"""Unit tests for process-global python-oracledb mode preparation."""

import threading
import time
import unittest
from unittest.mock import Mock

import gitdata.oracle_client as oracle_client


class DriverErrorDetail:
    """Fake public error detail exposed in a driver exception's arguments."""

    def __init__(self, full_code, message):
        self.full_code = full_code
        self.message = message


class DriverError(Exception):
    """Fake python-oracledb initialization error."""

    def __init__(self, full_code, message):
        super().__init__(DriverErrorDetail(full_code, message))


class FakeDriver:
    """Small stateful stand-in for python-oracledb's process mode."""

    Error = DriverError

    def __init__(self, thin=True, init_error=None, init_delay=0.0):
        self.thin = thin
        self.init_error = init_error
        self.init_delay = init_delay
        self.init_calls = 0
        self._calls_lock = threading.Lock()

    def is_thin_mode(self):
        return self.thin

    def init_oracle_client(self):
        with self._calls_lock:
            self.init_calls += 1
        if self.init_delay:
            time.sleep(self.init_delay)
        if self.init_error:
            raise self.init_error
        self.thin = False


class OracleClientTests(unittest.TestCase):

    def setUp(self):
        self.oracle_client = oracle_client

    def test_plain_reference_does_not_request_mode_change(self):
        driver = Mock()

        self.oracle_client.prepare_oracle_client(driver, thick=False)

        driver.is_thin_mode.assert_not_called()
        driver.init_oracle_client.assert_not_called()

    def test_already_thick_process_needs_no_initialization(self):
        driver = FakeDriver(thin=False)

        self.oracle_client.prepare_oracle_client(driver, thick=True)

        self.assertEqual(driver.init_calls, 0)

    def test_concurrent_external_thick_initialization_is_accepted(self):
        driver = Mock()
        driver.Error = DriverError
        driver.is_thin_mode.side_effect = [True, False]
        driver.init_oracle_client.side_effect = DriverError(
            'DPY-2017',
            'init_oracle_client() was already called with different arguments',
        )

        self.oracle_client.prepare_oracle_client(driver, thick=True)

        driver.init_oracle_client.assert_called_once_with()

    def test_thick_initialization_is_once_across_concurrent_callers(self):
        driver = FakeDriver(init_delay=0.05)
        caller_count = 12
        start = threading.Barrier(caller_count)
        errors = []

        def prepare():
            try:
                start.wait()
                self.oracle_client.prepare_oracle_client(driver, thick=True)
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)

        threads = [threading.Thread(target=prepare) for _ in range(caller_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        self.assertFalse(errors)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(driver.init_calls, 1)
        self.assertFalse(driver.is_thin_mode())

    def test_plain_connection_cannot_commit_thin_during_thick_initialization(self):
        driver = FakeDriver()
        init_started = threading.Event()
        allow_init = threading.Event()
        thin_connection_created = threading.Event()
        connections = []
        errors = []

        def initialize():
            driver.init_calls += 1
            init_started.set()
            allow_init.wait(timeout=2)
            if thin_connection_created.is_set():
                raise DriverError('DPY-2019', 'Thin mode already enabled')
            driver.thin = False

        def connect(name):
            if driver.thin:
                thin_connection_created.set()
            connections.append(name)
            return name

        driver.init_oracle_client = initialize
        setattr(driver, 'connect', connect)

        def open_connection(name, thick):
            try:
                connect_oracle = getattr(self.oracle_client, 'connect_oracle')
                connect_oracle(driver, thick, name)
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)

        thick_thread = threading.Thread(
            target=open_connection, args=('thick', True)
        )
        thick_thread.start()
        self.assertTrue(init_started.wait(timeout=1))

        plain_thread = threading.Thread(
            target=open_connection, args=('plain', False)
        )
        plain_thread.start()
        time.sleep(0.05)
        self.assertFalse(thin_connection_created.is_set())

        allow_init.set()
        thick_thread.join(timeout=2)
        plain_thread.join(timeout=2)

        self.assertFalse(errors)
        self.assertFalse(thick_thread.is_alive())
        self.assertFalse(plain_thread.is_alive())
        self.assertEqual(driver.init_calls, 1)
        self.assertCountEqual(connections, ['thick', 'plain'])

    def test_already_thin_process_reports_restart_requirement(self):
        driver = FakeDriver(
            init_error=DriverError(
                'DPY-2019',
                'python-oracledb thick mode cannot be used because thin mode '
                'has already been enabled',
            )
        )

        with self.assertRaises(self.oracle_client.OracleClientError) as raised:
            self.oracle_client.prepare_oracle_client(driver, thick=True)

        message = str(raised.exception)
        self.assertIn('already started in Thin mode', message)
        self.assertIn('restart', message.lower())
        self.assertNotIn('Instant Client', message)
        self.assertNotIn('DPY-2019', message)

    def test_unexpected_initialization_error_is_not_hidden(self):
        driver = FakeDriver(init_error=RuntimeError('programming defect'))

        with self.assertRaisesRegex(RuntimeError, 'programming defect'):
            self.oracle_client.prepare_oracle_client(driver, thick=True)

    def test_client_loading_failure_is_sanitized(self):
        driver = FakeDriver(
            init_error=DriverError(
                'DPI-1047',
                'Cannot locate a 64-bit Oracle Client library in /private/path',
            )
        )

        with self.assertRaises(self.oracle_client.OracleClientError) as raised:
            self.oracle_client.prepare_oracle_client(driver, thick=True)

        message = str(raised.exception)
        self.assertIn('Oracle Client libraries', message)
        self.assertNotIn('DPI-1047', message)
        self.assertNotIn('/private/path', message)


if __name__ == '__main__':
    unittest.main()
