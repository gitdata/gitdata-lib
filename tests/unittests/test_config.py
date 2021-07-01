"""
    gitdata config tests
"""

import os
import unittest

os.environ['GITDATA_EMAIL_HOST'] = 'myhost'

import gitdata.config


class ConfigTests(unittest.TestCase):

    def setUp(self):
        os.environ['GITDATA_TEST_VAR'] = 'foo'
        self.save_dir = os.getcwd()
        os.chdir(os.path.dirname(__file__))

    def tearDown(self):
        os.chdir(self.save_dir)

    def test_environment_variable(self):
        self.assertEqual(gitdata.config.get('GITDATA_TEST_VAR'), 'foo')

    def test_instance_setting(self):
        self.assertEqual(gitdata.config.get('TIME_ZONE'), 'UTM')
        # self.assertEqual(gitdata.config.get('EMAIL_HOST'), 'myhost')