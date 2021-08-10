"""
    gitdata config

    GitData looks for a configuration file named gitdata.ini to determine
    it's working configuration.  This file can be located in the current
    directory or any parent directory of the current directory, or
    if it's not found there it can be located in the user home
    directory or any parent of that directory.

    Environment variables can be used to override configuration file
    settings or to provide values where no configuration file exists
    or where the setting is not set.

    If the file cannot be found the default values will be used where
    possible.

    These config settings are determined once when the system is
    started.  To change them the system must be restarted.
"""

import configparser
import logging
import os
from os.path import join, exists, expanduser
from dotenv import load_dotenv

from gitdata.utils import parents, OrderedSet


logger = logging.getLogger(__name__)

load_dotenv()


class MissingConfigValueException(Exception):
    """Missing config value"""


class UndefinedConfigValueError(Exception):
    """Required config value missing"""


def read_config(pathname):
    """Read a config file into a Config parser"""
    logger.debug('reading config: %r', pathname)
    if os.path.exists(pathname):
        config = configparser.ConfigParser(strict=False)
        config.read(pathname)
        return config


class Config:
    """Config file parser
    """

    def __init__(self, pathname):
        self.pathname = pathname
        self.config = read_config(pathname)

    def get(self, key, cast=None, default=None, required=False):
        """Get a config value"""

        if '.' in key:
            section, option = key.split('.', 1)
        else:
            section, option = 'settings', key

        if self.config.has_option(section, option):
            value = self.config.get(section, option)

        elif default is not None:
            value = default

        elif required:
            raise MissingConfigValueException(
                'Unable to read %s from config:\n%s' % (
                    key,
                    self.pathname,
                )
            )

        else:
            return None

        return cast(value) if value is not None and cast else value

    def items(self):
        """Return a list of (name, value) tuples for each option in a section.

        Both the site config and the default sites config files are read and
        the results combined to produce the list of tuples.
        """
        result = {}
        for section in self.config.sections():
            for k, v in self.config.items(section):
                result[section + '.' + k] = v

        return list(result.items())

    def __str__(self):
        name = self.__class__.__name__
        t = []

        items = [
            (key, getattr(self, key, None)) for key, _ in self.items()
            if not key.startswith('_') or 'secret' in key.lower()
        ]

        for key, value in items:
            if callable(value):
                v = value()
            else:
                v = value
            t.append('  {} {}: {!r}'.format(
                key,
                '.'*(22-len(key[:22])),
                v
            ))
        return '\n'.join([name] + t)

    def __repr__(self):
        name = self.__class__.__name__
        t = []

        items = [
            (key, getattr(self, key, None)) for key, _ in self.items()
            if not key.startswith('_') or 'secret' in key.lower()
        ]

        for key, value in items:
            if callable(value):
                v = value()
            else:
                v = value
            t.append((repr(key), repr(v)))
        return '<%s {%s}>' % (
            name, ', '.join('%s: %s' % (k, v) for k, v in t)
        )


def locate_config_file(filename='gitdata.ini', start='.'):
    """locate a config file

    First look in the current directory or above and then look
    in the user root directory and above.
    """

    ancestors = OrderedSet(parents(start))
    for path in ancestors:
        pathname = join(path, filename)
        if exists(pathname):
            return pathname

    for path in OrderedSet(parents(join(expanduser('~')))) - ancestors:
        print(path)
        pathname = join(path, filename)
        if exists(pathname):
            return pathname


def load_config(start='.'):
    """Load a config file from a given starting location"""
    _config_location = locate_config_file(start=start)
    return Config(_config_location) if _config_location else None


_config = load_config()


def get(key, cast=None, default=None, required=False):
    """get configuration variable by key

    The gitdata.config.get function tries a variety of places to satisfy
    the request for a configuration setting.  They are:

      1. the environment
      --- more coming ---

    The cast callable can be used to cast the value into a desired type.

    All key have a default value except for any key that contains the word
    'SECRET'.  If a source in the stack returns None the function will keep
    looking until one of the sources either returns None or until the sources
    are exausted.

    >>> os.environ['MY_SETTING'] = 'one'
    >>> get('MY_SETTING')
    'one'

    >>> os.environ['MY_SETTING'] = '3'
    >>> get('MY_SETTING', cast=int)
    3

    >>> get('NO_SETTING')

    >>> get('NO_SETTING', default='3', cast=float)
    3.0

    >>> got_it = False
    >>> try:
    ...     get('MISSING_SECRET')
    ... except UndefinedConfigValueError:
    ...     got_it = True
    >>> got_it
    True


    """

    value = (
        os.environ.get(key)
        or (_config.get(key) if _config else None)
    )

    if value is None:
        if required or 'SECRET' in key:
            msg = 'Required config definition {} missing'
            raise UndefinedConfigValueError(msg.format(key))

    value = value if value is not None else default

    return cast(value) if value is not None and cast else value
