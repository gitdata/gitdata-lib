"""
    gitdata utils
"""

import inspect
import os

import gitdata


def libpath(*args):
    """Returns the location of a standard gitdata-lib asset

    >>> import os
    >>> asset_path = libpath('gitdata', 'assets', 'README.md')
    >>> os.path.exists(asset_path)
    True

    """
    realpath = os.path.realpath
    dirname = os.path.dirname
    join = os.path.join
    return realpath(join(realpath(dirname(gitdata.__file__)), '..', *args))


def thispath(*args):
    """Returns a location in the same directory as the

    >>> path = thispath('file.py')

    """
    realpath = os.path.realpath
    join = os.path.join
    root = realpath(os.path.dirname(inspect.stack()[1][1]))
    return join(root, *args)


def obfuscate(text):
    """obfuscate text so it is recognizable without divulging it

    >>> obfuscate('12345')
    '1***5'

    >>> obfuscate('')
    ''

    """
    return text[:1] + '*' * (len(text) - 2) + text[-1:]


def parents(path):
    """Return list of parent directories"""
    if not os.path.isdir(path):
        return parents(os.path.split(os.path.abspath(path))[0])
    parent = os.path.abspath(os.path.join(path, os.pardir))
    if path == parent:
        return []
    else:
        return [path] + parents(parent)
