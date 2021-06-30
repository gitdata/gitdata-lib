"""
    gitdata utils
"""

import inspect
import logging
import os

import gitdata


logger = logging.getLogger(__name__)


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


def sorted_column_names(names):
    """Return column names sorted in a more typically expected order"""

    def looks_like_an_id(text):
        return text.endswith('_id')

    id_names = sorted(name for name in names if looks_like_an_id(name))
    special_names = id_names + [
        'id', 'userid', 'groupid', 'key',
        'name', 'title', 'description',
        'first_name', 'middle_name', 'last_name', 'fname', 'lname'
    ]
    result = []
    for name in special_names:
        if name in names:
            result.append(name)
    for name in sorted(names, key=lambda a: (len(a), a)):
        if name not in result:
            result.append(name)
    return result


class Record(dict):
    """Record Class

    A dict that provides attribute access, printability and
    attribute access.

    >>> import decimal
    >>> class Person(Record):
    ...    @property
    ...    def full_name(self):
    ...        return ' '.join([self.name, self.surname])
    >>> joe = Person(name='Joe', surname='Smith')
    >>> joe.name
    'Joe'
    >>> joe['name']
    'Joe'

    >>> joe.age = 20
    >>> joe['age']
    20

    >>> joe.full_name
    'Joe Smith'

    >>> del joe.age
    >>> joe.age

    >>> try:
    ...     del joe.missing
    ... except AttributeError:
    ...     print('missing attribute cannot be deleted!')
    missing attribute cannot be deleted!


    >>> try:
    ...     joe.missing
    ... except KeyError:
    ...     print('missing attribute should not raise exception!')

    >>> joe.missing

    >>> print(Person(name='Pat', surname='Jones', age=21, salary=decimal.Decimal(1000)))
    Person
      name ................: 'Pat'
      age .................: 21
      salary ..............: Decimal('1000')
      surname .............: 'Jones'
      full_name ...........: 'Pat Jones'

    >>> Person(name='Pat', surname='Jones', age=21, salary=decimal.Decimal(1000))
    <Person {'name': 'Pat', 'age': 21, 'salary': Decimal('1000'), 'surname': 'Jones', 'full_name': 'Pat Jones'}>

    """

    __setattr__ = dict.__setitem__

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except KeyError:
            return None

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError as k:
            raise AttributeError from k

    def attributes(self):
        """Return propoerties and members as one set"""

        def properties():
            items = self.__class__.__dict__.items()
            return [k for k, v in items if isinstance(v, property)]

        names = list(self.keys()) + properties()
        return sorted_column_names(names)

    def __str__(self):
        name = self.__class__.__name__
        attributes = self.attributes()
        t = []

        items = [
            (key, getattr(self, key, None)) for key in attributes
            if not key.startswith('_')
        ]

        for key, value in items:
            if callable(value):
                v = value()
            else:
                v = value
            t.append('  {} {}: {!r}'.format(
                key,
                '.'*(20-len(key[:20])),
                v
            ))
        return '\n'.join([name] + t)

    def __repr__(self):
        name = self.__class__.__name__
        attributes = self.attributes()
        t = []

        items = [
            (key, getattr(self, key, None)) for key in attributes
            if not key.startswith('_')
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

    def save(self):
        """save record to originating store"""
        record_id = self['__store'].put(self)
        key = self['__store'].id_name
        logger.debug(
            'saved record %s(%s=%r) to %r',
            self.__class__.__name__,
            key,
            self[key],
            self['__store']
        )
        return record_id
