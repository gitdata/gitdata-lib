"""Packaging tests for optional database drivers."""

import os
import runpy
import unittest
from unittest.mock import patch


class TestOraclePackaging(unittest.TestCase):

    def setup_arguments(self):
        setup_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'setup.py',
        )

        with patch('setuptools.setup') as setup:
            runpy.run_path(setup_path, run_name='__main__')

        return setup.call_args.kwargs

    def test_oracle_driver_is_an_optional_extra(self):
        arguments = self.setup_arguments()
        oracle_requirements = arguments['extras_require']['oracle']
        self.assertTrue(
            any(requirement.startswith('oracledb')
                for requirement in oracle_requirements)
        )
        self.assertFalse(
            any(requirement.startswith('oracledb')
                for requirement in arguments['install_requires'])
        )

    def test_package_targets_python_39_only(self):
        arguments = self.setup_arguments()

        self.assertEqual(arguments['python_requires'], '>=3.9,<3.10')
        classifiers = arguments['classifiers']
        self.assertIn('Programming Language :: Python :: 3.9', classifiers)
        for unsupported in ('3.6', '3.7', '3.8'):
            self.assertNotIn(
                'Programming Language :: Python :: {}'.format(unsupported),
                classifiers,
            )
