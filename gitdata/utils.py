"""
    gitdata utils
"""

import collections
import datetime
import decimal
import inspect
import logging
import os
import uuid


logger = logging.getLogger(__name__)


def new_uid():
    """returns a unique id"""
    return uuid.uuid4().hex


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


def trim(text):
    """Remove excess spaces from a block of text

    >>> trim('remove right ')
    'remove right'

    >>> trim(' remove left')
    'remove left'

    >>> print(trim(' remove spaces\\n    from block\\n    of text'))
    remove spaces
       from block
       of text

    >>> print(
    ...     trim(
    ...     '    \\n'
    ...     '    remove spaces\\n'
    ...     '        from block\\n'
    ...     '        of text\\n'
    ...     '    \\n'
    ...     '\\n'
    ...     )
    ... )
    <BLANKLINE>
    remove spaces
        from block
        of text
    <BLANKLINE>
    <BLANKLINE>

    >>> print(trim('    remove spaces\\n  from block\\n  of text\\n    '))
      remove spaces
    from block
    of text
    <BLANKLINE>

    >>> print(trim('    remove spaces\\n  from block\\n  of text'))
      remove spaces
    from block
    of text

    >>> print(trim('\\n  remove spaces\\n    from block\\n  of text'))
    <BLANKLINE>
    remove spaces
      from block
    of text

    >>> text = '\\nremove spaces  \\n    from block\\nof text'
    >>> print('\\n'.join(repr(t) for t in trim(text).splitlines()))
    'remove spaces  '
    '    from block'
    'of text'

    >>> text = (
    ...     '\\nremove spaces'
    ...     '\\n    from block'
    ... )
    >>> print(trim(text))
    remove spaces
        from block

    """
    trim_size = None
    lines = text.splitlines()
    for line in lines:
        if not line or line.isspace():
            continue
        n = len(line) - len(line.lstrip())
        trim_size = min([trim_size, n]) if trim_size is not None else n
    if trim_size:
        result = []
        for line in lines:
            result.append(line[trim_size:])
        return '\n'.join(result)
    else:
        return text.strip()


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


def kind(o):
    """
    returns a text version of an object class name
    """
    n = []
    for c in o.__class__.__name__:
        if c.isalpha() or c == '_':
            if c.isupper() and len(n):
                n.append('_')
            n.append(c.lower())
    return ''.join(n)


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
        return get_attributes(self)

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


def get_properties(obj):
    if type(obj) == dict:
        return []
    klass = obj.__class__
    return [
        i for i, j in (
            (n, getattr(klass, n)) for n in dir(klass)
        ) if type(j) == property
    ]


def get_attributes(obj):
    names = list(obj.keys()) + get_properties(obj)
    return sorted_column_names(names)


class RecordList(list):
    """a list of Records"""

    def __init__(self, *a, **k):
        list.__init__(self, *a, **k)
        self._n = 0

    def __iter__(self):
        self._n = 0
        return self

    def __next__(self):
        if self._n >= len(self):
            raise StopIteration
        else:
            result = self[self._n]
            self._n += 1
        return result

    def __str__(self):
        """
        represent as a string

        >>> import datetime
        >>> class Person(Record): pass
        >>> class People(RecordList): pass
        >>> people = People()
        >>> people.append(Person(_id=1, name='Joe', age=20,
        ...     birthdate=datetime.date(1992,5,5)))
        >>> people.append(Person(_id=2, name='Samuel', age=25,
        ...     birthdate=datetime.date(1992,4,5)))
        >>> people.append(Person(_id=3, name='Sam', age=35,
        ...     birthdate=datetime.date(1992,3,5)))
        >>> print(people)
        person
        _id name   age birthdate
        --- ------ --- ----------
          1 Joe     20 1992-05-05
          2 Samuel  25 1992-04-05
          3 Sam     35 1992-03-05
        3 person records

        >>> class Player(Person):
        ...    @property
        ...    def score(self):
        ...        return 10
        >>> people = People()
        >>> people.append(Player(userid=1, name='Joe', age=20,
        ...     birthdate=datetime.date(1992,5,5)))
        >>> people.append(Player(userid=2, name='Samuel', age=25,
        ...     birthdate=datetime.date(1992,4,5)))
        >>> people.append(Player(userid=3, name='Sam', age=35,
        ...     birthdate=datetime.date(1992,3,5)))
        >>> print(people)
        player
        userid name   age score birthdate
        ------ ------ --- ----- ----------
             1 Joe     20    10 1992-05-05
             2 Samuel  25    10 1992-04-05
             3 Sam     35    10 1992-03-05
        3 player records

        """

        def visible(name):
            return not name.startswith('__')

        if not bool(self):
            return 'Empty list'

        title = '%s\n' % kind(self[0])

        keys = labels = list(filter(visible, get_attributes(self[0])))
        rows = [[getattr(record, key, record.get(key)) for key in keys] for record in self]

        footer = '\n{} {} records'.format(len(self), kind(self[0]))

        return title + str(ItemList(rows, labels=labels)) + footer


class OrderedSet(collections.MutableSet):
    """OrderedSet

    A set that preserves the order of the elements

    >>> s = OrderedSet('abracadaba')
    >>> t = OrderedSet('simsalabim')
    >>> print(s | t)
    OrderedSet(['a', 'b', 'r', 'c', 'd', 's', 'i', 'm', 'l'])
    >>> print(s & t)
    OrderedSet(['a', 'b'])
    >>> print(s - t)
    OrderedSet(['r', 'c', 'd'])
    >>> print(OrderedSet(reversed(s - t)))
    OrderedSet(['d', 'c', 'r'])
    >>> OrderedSet(['d', 'c', 'd']) == OrderedSet(['c', 'd', 'd'])
    False

    credit: http://code.activestate.com/recipes/576694/
    Licensed under MIT License
    """

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        """test if item is present

            >>> s = OrderedSet([1, 2, 3])
            >>> 'c' in s
            False
            >>> 2 in s
            True
        """
        return key in self.map

    def add(self, key):
        """add an item

            >>> s = OrderedSet([1, 2, 3])
            >>> s.add(4)
            >>> s
            OrderedSet([1, 2, 3, 4])
        """
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        """discard an item by key

            >>> s = OrderedSet([1, 2, 3])
            >>> s.discard(1)
            >>> s
            OrderedSet([2, 3])
        """
        if key in self.map:
            key, prev, _next = self.map.pop(key)
            prev[2] = _next
            _next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        """pop an item

            >>> s = OrderedSet([1, 2, 3])
            >>> s.pop(2)
            3
            >>> s
            OrderedSet([1, 2])
        """
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)
