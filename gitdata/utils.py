"""
    gitdata utils
"""

import datetime
import decimal
import inspect
import logging
import os


logger = logging.getLogger(__name__)


def libpath(*args):
    """Returns the location of a standard gitdata-lib asset

    >>> import os
    >>> asset_path = libpath('assets', 'README.md')
    >>> os.path.exists(asset_path)
    True

    """
    realpath = os.path.realpath
    dirname = os.path.dirname
    join = os.path.join
    return realpath(join(realpath(dirname(__file__)), *args))


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


class Bunch:
    """a handy bunch of variables

    >>> something = Bunch(name='Cat', colour='Brown')
    >>> something.name
    'Cat'
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


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

    def __getitem__(self, name):
        try:
            value = dict.__getitem__(self, name)
            if hasattr(value, '__get__'):
                getter = getattr(value, '__get__')
                if getter is not None:
                    return getter(self)
                else:
                    return value
            else:
                return value
        except KeyError as k:
            try:
                value = self.__class__.__dict__[name]
                if hasattr(value, '__get__'):
                    getter = getattr(value, '__get__')
                    if getter:
                        return getter(self)
                    else:
                        return value
                else:
                    return value
            except KeyError as k:
                raise k

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


class ItemList(list):
    """
    list of data items

    >>> items = ItemList()
    >>> items.append(['Joe', 12, 125])
    >>> items
    [['Joe', 12, 125]]
    >>> print(items)
    Column 0 Column 1 Column 2
    -------- -------- --------
    Joe            12      125

    >>> items.insert(0, ['Name', 'Score', 'Points'])
    >>> print(items)
    Name Score Points
    ---- ----- ------
    Joe     12    125

    >>> data = [
    ...     ['Joe', 12, 125],
    ...     ['Sally', 13, 1354],
    ... ]
    >>> items = ItemList(data)
    >>> print(items)
    Column 0 Column 1 Column 2
    -------- -------- --------
    Joe            12      125
    Sally          13    1,354

    >>> data = [
    ...     ['Joe', 12, 125],
    ...     ['Sally', 13, 135],
    ... ]
    >>> items = ItemList(data, labels=['Name', 'Score', 'Points'])
    >>> print(items)
    Name  Score Points
    ----- ----- ------
    Joe      12    125
    Sally    13    135

    >>> data = [
    ...     [10000, 'Joe', 12, 125],
    ...     [10001, 'Sally', 13, 135],
    ... ]
    >>> items = ItemList(data, labels=['_id', 'Name', 'Score', 'Points'])
    >>> print(items)
    _id   Name  Score Points
    ----- ----- ----- ------
    10000 Joe      12    125
    10001 Sally    13    135

    >>> now = datetime.date(2020, 2, 1)
    >>> data = [
    ...     [10000, 'Joe', now - datetime.date(1980, 1, 20)],
    ...     [10001, 'Sally', now - datetime.date(1984, 9, 20)],
    ... ]
    >>> items = ItemList(data, labels=['_id', 'Name', 'Age'])
    >>> print(items)
    _id   Name  Age
    ----- ----- -------------------
    10000 Joe   14622 days, 0:00:00
    10001 Sally 12917 days, 0:00:00

    >>> now = datetime.date(2020, 2, 1)
    >>> data = [
    ...     [10000, 'Joe', now - datetime.date(1980, 1, 20)],
    ...     [10001, 'Sally', now - datetime.date(1984, 9, 20)],
    ... ]
    >>> items = ItemList(data, labels=['user_id', 'Name', 'Age'])
    >>> print(items)
    user_id Name  Age
    ------- ----- -------------------
      10000 Joe   14622 days, 0:00:00
      10001 Sally 12917 days, 0:00:00

    >>> import datetime
    >>> now = datetime.date(2020, 2, 1)
    >>> data = [
    ...     [9000, 'Greens', 1234],
    ...     [10000, 'Browns', 1203],
    ... ]
    >>> items = ItemList(data, labels=['id', 'customer', 'invoice_number'])
    >>> print(items)
    id    customer invoice_number
    ----- -------- --------------
     9000 Greens             1234
    10000 Browns             1203
    """
    def __init__(self, *args, **kwargs):
        self.labels = kwargs.pop('labels', None)
        list.__init__(self, *args, **kwargs)

    def __str__(self):
        def is_text(value):
            return type(value) in [str, bytes]

        def name_column(number):
            return 'Column {}'.format(number)

        def is_homogeneous(values):
            return any([
                len(values) <= 1,
                all(type(values[0]) == type(i) for i in values[1:]),
            ])

        def get_format(label, values):
            first_non_null = list(
                map(type, [a for a in values if a is not None])
            )[:1]
            if first_non_null:
                data_type = first_non_null[0]
                if label in ['_id', 'userid']:
                    return '{:>{width}}'
                elif label == 'id':
                    return '{:>{width}}'
                elif label.endswith('_id'):
                    return '{:>{width}}'
                elif label.endswith('_number'):
                    return '{:>{width}}'
                elif data_type in [int, float, decimal.Decimal]:
                    return '{:{width},}'
                elif data_type in [datetime.date]:
                    return '{:%Y-%m-%d}'
                elif data_type in [datetime.timedelta]:
                    return '{:}'
                elif data_type in [datetime.datetime]:
                    return '{:%Y-%m-%d %H:%M:%S}'
            return '{:<{width}}'

        def nvl(value):
            if value is None:
                return 'None'
            return value

        if len(self) == 0:
            return ''

        num_columns = len(list(self[0]))
        columns = list(range(num_columns))

        # calculate labels
        if self.labels:
            labels = self.labels
            offset = 0
        else:
            if not all(is_text(label) for label in self[0]):
                labels = [name_column(i) for i in range(num_columns)]
                offset = 0
            else:
                labels = self[0]
                offset = 1

        # rows containing data
        rows = [list(nvl(v) for v in row) for row in self[offset:]]

        # calculate formats
        formats = []
        for col in columns:
            values = [row[col] for row in rows]
            if is_homogeneous(values):
                formats.append(get_format(labels[col], values))
            else:
                formats.append('{}')

        # calulate formatted values
        formatted_values = [labels] + [
            [
                formats[col].format(row[col], width=0)
                for col in columns
            ] for row in rows
        ]

        # calculate column widths
        data_widths = {}
        for row in formatted_values:
            for col in columns:
                n = data_widths.get(col, 0)
                m = len(row[col])
                if n < m:
                    data_widths[col] = m

        label_format = '{:<{width}}'
        formatted_labels = [
            label_format.format(l, width=data_widths[i])
            for i, l in enumerate(labels)
        ]

        sorted_names = sorted_column_names(labels)

        for i, v in enumerate(formats):
            formats[i] = v if v != '{}' else '{:<{width}}'

        if not self.labels:
            columns = sorted(columns, key=lambda a: sorted_names.index(labels[a]))
        dashes = ['-' * data_widths[col] for col in columns]
        sorted_labels = [formatted_labels[col] for col in columns]

        aligned_rows = [sorted_labels] + [dashes] + [
            [
                formats[col].format(row[col], width=data_widths[col])
                for col in columns
            ] for row in rows
        ]

        lines = [' '.join(row).rstrip() for row in aligned_rows]

        return '\n'.join(lines)
