"""Encryption tests."""

# pylint: disable=missing-docstring
# pylint: disable=invalid-name
# It's reasonable in this case.

import unittest

import gitdata.encryption as encryption


class TestEncryption(unittest.TestCase):
    """Test encryption utilities."""

    def setUp(self):
        self.key = encryption.generate_key()
        self.encrypter = encryption.get_encrypter(self.key)

    def test_generate_key(self):
        key = encryption.generate_key()
        self.assertEqual(type(key), type(b''))
        self.assertEqual(len(key), 44)

    def test_encrypt_decrypt(self):
        my_sensitive_data = 'my data'
        my_encrypted_sensitive_data = self.encrypter.encrypt(my_sensitive_data)
        self.assertNotEqual(my_sensitive_data, my_encrypted_sensitive_data)
        self.assertEqual(my_sensitive_data, self.encrypter.decrypt(my_encrypted_sensitive_data))
