"""
    gitdata config tests
"""

import os
import unittest

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
        start = os.path.dirname(__file__)
        config_file_pathname = gitdata.config.locate_config_file(start=start)
        config = gitdata.config.load_config(config_file_pathname)
        self.assertEqual(config.get('email.host'), 'mail.mailer.com')

    def test_config_key_name(self):
        start = os.path.dirname(__file__)
        config_file_pathname = gitdata.config.locate_config_file(start=start)
        config = gitdata.config.load_config(config_file_pathname)
        self.assertEqual(config.get('database.engine.host'), 'localhost')

    def test_config_cast(self):
        start = os.path.dirname(__file__)
        config_file_pathname = gitdata.config.locate_config_file(start=start)
        config = gitdata.config.load_config(config_file_pathname)
        self.assertEqual(config.get('email.port', cast=int), 22)

    def test_read_user_config(self):
        start = os.path.dirname(__file__)
        config_file_pathname = gitdata.config.locate_config_file(filename='.gitdata', start=start)
        config = gitdata.config.Config(config_file_pathname)
        self.assertEqual(config.get('user.time_zone'), 'America/Pacific')
