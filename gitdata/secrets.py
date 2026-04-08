"""gitdata secrets."""

import os
import copy
from dataclasses import dataclass

from gitdata.encryption import get_encrypter


DEFAULT_ENCRYPTION_KEY_NAME = 'gitdata_encryption_key'
DEFAULT_SECRETS_PATH = '/run/secrets'
ENCRYPTION_KEY_ENV_VAR = 'GITDATA_ENCRYPTION_KEY'


class SecretsKeyMissingException(Exception):
    """Raised when secrets encryption key is missing."""


@dataclass
class Secret:
    """Simple secret record."""

    name: str
    value: object
    expiry: object = None


class InMemorySecretsStorage:
    """In-memory storage backend for secrets.

    Serves as the reference implementation for the storage contract used by
    ``Secrets``.
    """

    def __init__(self):
        self._records = {}

    def put(self, record):
        self._records[record.name] = record
        return record

    def first(self, **kv):
        name = kv.get('name')
        return self._records.get(name)

    def delete(self, **kv):
        name = kv.get('name')
        self._records.pop(name, None)

    def __iter__(self):
        return iter(self._records.values())

    def __len__(self):
        return len(self._records)


def _to_key_bytes(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.strip().encode('utf-8')
    msg = 'Unsupported encryption key type: {}'
    raise TypeError(msg.format(type(value).__name__))


def get_encryption_key(
    key_name=DEFAULT_ENCRYPTION_KEY_NAME,
    secrets_path=DEFAULT_SECRETS_PATH,
):
    """Get encryption key from docker secrets path or env var."""

    if key_name and os.path.basename(key_name) == key_name:
        pathname = os.path.join(secrets_path, key_name)
        if os.path.isfile(pathname):
            with open(pathname, 'r', encoding='utf-8') as f:
                return _to_key_bytes(f.read())

    return _to_key_bytes(os.environ.get(ENCRYPTION_KEY_ENV_VAR))


def get_secrets_encrypter(key=None, key_name=DEFAULT_ENCRYPTION_KEY_NAME):
    """Get an encrypter for secrets operations."""

    resolved_key = _to_key_bytes(key) or get_encryption_key(key_name=key_name)
    if not resolved_key:
        raise SecretsKeyMissingException('Secrets encryption key missing')
    return get_encrypter(resolved_key)


def _record_value(record):
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get('value')
    return getattr(record, 'value', None)


def _set_record_value(record, value):
    if record is None:
        return None
    if isinstance(record, dict):
        record['value'] = value
        return record
    record.value = value
    return record


def _copy_record(record):
    if record is None:
        return None
    if isinstance(record, dict):
        return dict(record)
    try:
        return copy.copy(record)
    except Exception:  # pragma: no cover - defensive fallback
        return Secret(
            name=getattr(record, 'name', None),
            value=_record_value(record),
            expiry=getattr(record, 'expiry', None),
        )


class Secrets:
    """Encrypted secrets manager with pluggable storage backend.

    Expected storage contract (duck-typed):
    - ``put(record)``: stores and returns a record with at least ``name`` and ``value``
    - ``first(name=<str>)``: returns one matching record or ``None``
    - ``delete(name=<str>)``: deletes by name (should be safe if missing)
    - ``__iter__()``: yields records
    - ``__len__()``: returns number of stored records

    Records may be objects (with ``name``/``value`` attributes) or dict-like
    objects (with ``'name'``/``'value'`` keys).
    """

    def __init__(self, key=None, storage=None, key_name=DEFAULT_ENCRYPTION_KEY_NAME):
        self.storage = storage or InMemorySecretsStorage()
        self.encrypter = get_secrets_encrypter(key=key, key_name=key_name)

    def _decrypt_value(self, value):
        if isinstance(value, (bytes, bytearray)):
            return self.encrypter.decrypt(value)
        return value

    def _public_record(self, record, reveal=False):
        result = _copy_record(record)
        value = _record_value(record)
        if reveal:
            value = self._decrypt_value(value)
        else:
            value = None if value is None else '****'
        return _set_record_value(result, value)

    def set(self, name, value, expiry=None):
        record = Secret(
            name=name,
            value=self.encrypter.encrypt(value),
            expiry=expiry,
        )
        self.storage.put(record)
        return record.value

    def get(self, name):
        record = self.storage.first(name=name)
        if record is None:
            return None
        return self._decrypt_value(_record_value(record))

    def delete(self, name):
        self.storage.delete(name=name)

    def keys(self):
        return list(record.name for record in self.storage)

    def list(self, reveal=False):
        records = list(self.storage)
        return [self._public_record(record, reveal=reveal) for record in records]

    def first(self, name, reveal=False):
        record = self.storage.first(name=name)
        return self._public_record(record, reveal=reveal)

    def exists(self, name):
        return self.storage.first(name=name) is not None

    def get_or_set(self, name, default_value, expiry=None):
        value = self.get(name)
        if value is not None:
            return value
        self.set(name, default_value, expiry=expiry)
        return default_value

    def update(self, name, value):
        if not self.exists(name):
            raise KeyError(name)
        self.set(name, value)
        return value

    def rename(self, old_name, new_name):
        record = self.storage.first(name=old_name)
        if record is None:
            raise KeyError(old_name)
        value = self._decrypt_value(_record_value(record))
        expiry = record.get('expiry') if isinstance(record, dict) else getattr(record, 'expiry', None)
        self.delete(old_name)
        self.set(new_name, value, expiry=expiry)

    def pop(self, name):
        value = self.get(name)
        if value is None:
            return None
        self.delete(name)
        return value

    def clear(self):
        for name in list(self.keys()):
            self.delete(name)

    def __iter__(self):
        return iter(self.list())

    def __len__(self):
        return len(self.storage)


def get_secrets(key=None, storage=None, key_name=DEFAULT_ENCRYPTION_KEY_NAME):
    return Secrets(key=key, storage=storage, key_name=key_name)


def get_secret(name, key=None, storage=None, key_name=DEFAULT_ENCRYPTION_KEY_NAME):
    return get_secrets(key=key, storage=storage, key_name=key_name).get(name)


def set_secret(name, value, key=None, storage=None, key_name=DEFAULT_ENCRYPTION_KEY_NAME):
    return get_secrets(key=key, storage=storage, key_name=key_name).set(name, value)
