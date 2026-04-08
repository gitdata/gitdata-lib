"""gitdata encryption utilities."""

from cryptography.fernet import Fernet

def generate_key():
    """Generate a new key"""
    return Fernet.generate_key()


class Encrypter:

    def __init__(self, key):
        self.cypher = Fernet(key)

    def encrypt(self, value):
        encrypted_value = self.cypher.encrypt(value.encode('utf-8'))
        return encrypted_value

    def decrypt(self, encrypted_value):
        value = self.cypher.decrypt(encrypted_value).decode('utf-8')
        return value


def get_encrypter(key):
    return Encrypter(key)
