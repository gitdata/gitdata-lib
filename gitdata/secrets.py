"""
    gitdata secrets
"""

import gitdata.config

class Secrets:

    def __init__(self):
        self.storage = {}
        self.encrption_key = gitdata.config.get('ENCRYPTION_KEY')

    def set(self, name, value):
        self.storage[name] = value

    def get(self, name):
        return self.storage[name]

    def delete(self, name):
        del self.storage[name]

    def list(self):
        return list(self.storage.keys())

    def __len__(self):
        return len(self.storage)

def get_secrets():
    return Secrets()
