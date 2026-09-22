"""Packaging tests for optional database drivers."""

import os
import runpy
import unittest
from unittest.mock import patch


class TestOraclePackaging(unittest.TestCase):

    def test_oracle_driver_is_an_optional_extra(self):
        setup_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'setup.py',
        )

        with patch('setuptools.setup') as setup:
            runpy.run_path(setup_path, run_name='__main__')

        arguments = setup.call_args.kwargs
        oracle_requirements = arguments['extras_require']['oracle']
        self.assertTrue(
            any(requirement.startswith('oracledb')
                for requirement in oracle_requirements)
        )
        self.assertFalse(
            any(requirement.startswith('oracledb')
                for requirement in arguments['install_requires'])
        )
