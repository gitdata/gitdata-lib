"""
    gitdata instance config

    GitData looks for a configuration file named .gitdata to determine
    it's default settings.  This file can be located in the current
    directory or any parent directory of the current directory, or
    if it's not found there it can be located in the user home
    directory or any parent of that directory.

    Environment variables can be used to override configuration file
    settings or to provide values where no configuration file exists
    or where the setting is not set.

    If the file cannot be found the default values will be used.

    If more than one configuration file exists, settings in the files
    nearest to the current directory will override the settings in files
    that are further away.  In this way, general default settings can be
    provided with a top level config file and those settings can be
    selectively overridden for different environments by more locally
    defined config files.

    These config settings are determined once when the system is
    started.  To change them the system must be restarted.
"""

import os

from unipath import Path
from decouple import config, RepositoryIni

from gitdata.utils import parents


def locate(filename='gitdata.conf', start='.'):
    """locate a config file

    First look in the current directory or above and then look
    in the user root directory and above.
    """
    print('locating')
    for path in parents(start):
        pathname = os.path.join(path, filename)
        if os.path.exists(pathname):
            return pathname

    for path in parents(os.path.join(os.path.expanduser('~'))):
        pathname = os.path.join(path, filename)
        if os.path.exists(pathname):
            return pathname


config.SUPPORTED['gitdata.conf'] = RepositoryIni
# print(config.SUPPORTED)
config.search_path = locate()

BASE_DIR = Path(__file__).parent

def db_url(text):
    """Cast text to valid db url"""
    assert text
    return text

DATABASES = {
    'default': config(
        'DATABASE_URL',
        default='sqlite:///' + BASE_DIR.child('gitdata.sqlite3'),
        cast=db_url
    )
}

DEBUG = config('DEBUG', default=False, cast=bool)
TEMPLATE_DEBUG = DEBUG

TIME_ZONE = config('TIME_ZONE', 'America/Pacific')
USE_TZ = True

SECRET_KEY = config('SECRET_KEY')

EMAIL_HOST = config('GITDATA_EMAIL_HOST', default='localhost')
EMAIL_PORT = config('GITDATA_EMAIL_PORT', default=25, cast=int)
EMAIL_HOST_PASSWORD = config('GITDATA_EMAIL_HOST_PASSWORD', default='')
EMAIL_HOST_USER = config('GITDATA_EMAIL_HOST_USER', default='')
EMAIL_USE_TLS = config('GITDATA_EMAIL_USE_TLS', default=False, cast=bool)

def get(name):
    if name in os.environ:
        return os.environ[name]
    print('TIME_ZONE' in globals())
    if name in globals():
        return globals()[name]
