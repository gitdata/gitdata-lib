"""
    gitdata.stores.records

    Record Store

    A RecordStore is a high level class that makes working with relational
    database stores simpler.  Not to be confused with an ORM, a RecordStore
    performs basic database operations while staying out of your way if you
    need to do something more elborate.

    All of the gitdata.stores package Store classes operate on any dict which
    but are most commonly used with Records as defined in gitdata.utils.

"""

import datetime
import decimal

import gitdata
from gitdata.utils import Record, RecordList, kind
from gitdata.stores.entities import Store, UnsupportedTypeException


def get_result_iterator(rows, storage):
    """returns an iterator that iterates over the rows and zips the names onto
    the items being iterated so they come back as dicts"""
    cls = storage.record_class
    names = [d[0] == 'id' and '_id' or d[0] for d in rows.cursor.description]
    for rec in rows:
        yield cls(
            ((k, v) for k, v in zip(names, rec)),
            __store=storage,
        )


class Result(object):
    """rows resulting from a method call"""
    # pylint: disable=too-few-public-methods
    def __init__(self, rows, storage):
        self.rows = rows
        self.storage = storage

    def __iter__(self):
        return get_result_iterator(self.rows, self.storage)

    def __len__(self):
        return len(list(self.rows))

    def __repr__(self):
        return repr(list(get_result_iterator(self.rows, self.storage)))

    def __str__(self):
        records = list(get_result_iterator(self.rows, self.storage))
        return str(RecordList(records))


class RecordStore(Store):
    """stores records

    >>> db = gitdata.database.setup_test()

    >>> class Person(Record): pass
    >>> class People(RecordStore): pass
    >>> people = People(db, Person)
    >>> people.kind
    'person'

    >>> joe = Person(name='Joe', age=20, birthdate=datetime.date(1992,5,5))
    >>> print(joe)
    Person
      name ................: 'Joe'
      age .................: 20
      birthdate ...........: datetime.date(1992, 5, 5)

    >>> people.put(joe)
    1
    >>> person = people.get(1)
    >>> print(person)
    Person
      name ................: 'Joe'
      age .................: 20
      kids ................: None
      birthdate ...........: datetime.date(1992, 5, 5)

    """

    order_by = None

    def __init__(self, db, record_class=dict, name=None, key='id'):
        # pylint: disable=invalid-name
        self.db = db
        self.record_class = record_class
        self.kind = name or kind(record_class())
        self.key = key

    @property
    def id_name(self):
        return self.key == 'id' and '_id' or self.key

    def put(self, record):
        """
        stores a record

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> sally = Person(name='Sally', age=25)
        >>> sally
        <Person {'name': 'Sally', 'age': 25}>
        >>> id = people.put(Person(name='Sally', age=25))
        >>> id
        1
        >>> sally
        <Person {'name': 'Sally', 'age': 25}>
        >>> sally = people.get(id)
        >>> sally
        <Person {'name': 'Sally', 'age': 25, 'kids': None, 'birthdate': None}>
        >>> sally.age = 35
        >>> people.put(sally)
        1
        >>> person = people.get(id)
        >>> person
        <Person {'name': 'Sally', 'age': 35, 'kids': None, 'birthdate': None}>
        >>> id = people.put({'name':'James', 'age':15})
        >>> id
        2
        >>> people.get(id)
        <Person {'name': 'James', 'age': 15, 'kids': None, 'birthdate': None}>
        """

        updating = self.id_name in record
        if updating:
            self.before_update(record)
        else:
            self.before_insert(record)

        table_attributes = self.get_attributes()
        keys = [
            k for k in record.keys() if k != '_id' and k in table_attributes
        ]
        values = [record[k] for k in keys]
        datatypes = [type(i) for i in values]
        values = [i for i in values]
        valid_types = [
            str,
            bytes,
            int,
            float,
            datetime.date,
            datetime.datetime,
            bool,
            type(None),
            decimal.Decimal,
        ]

        for atype in datatypes:
            if atype not in valid_types:
                msg = 'unsupported type <type %s>' % atype
                raise UnsupportedTypeException(msg)

        if updating:
            _id = record[self.id_name]
            set_clause = ', '.join('`%s`=%s' % (i, '%s') for i in keys)
            cmd = 'update %s set %s where `%s`=%d' % (
                self.kind,
                set_clause,
                self.key,
                _id
            )
            self.db(cmd, *values)
        else:
            names = ', '.join('`%s`' % k for k in keys)
            placeholders = ','.join(['%s'] * len(keys))
            cmd = 'insert into %s (%s) values (%s)' % (
                self.kind, names, placeholders)
            _id = self.db(cmd, *values)
            record[self.id_name] = _id

        record['__store'] = self

        if updating:
            self.after_update(record)
        else:
            self.after_insert(record)

        return _id

    def get(self, keys):
        # pylint: disable=trailing-whitespace
        """
        retrives records

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(**{'name': 'Sam', 'age':15}))
        >>> sam = people.get(id)
        >>> sam
        <Person {'name': 'Sam', 'age': 15, 'kids': None, 'birthdate': None}>
        >>> people.put(Person(name='Jim',age=21))
        2
        >>> print(people)
        person
        _id name age kids birthdate
        --- ---- --- ---- ---------
          1 Sam   15 None None
          2 Jim   21 None None
        2 person records

        >>> people.put(Person(name='Alice',age=29))
        3
        >>> print(people.get([1, 3]))
        person
        _id name  age kids birthdate
        --- ----- --- ---- ---------
          1 Sam    15 None None
          3 Alice  29 None None
        2 person records

        """

        if keys is None:
            return None

        if not isinstance(keys, (list, tuple)):
            keys = (keys, )
            cmd = 'select * from '+self.kind+' where ' + self.key + '=%s'
            as_list = 0
        else:
            keys = [int(key) for key in keys]
            cmd = 'select * from {} where {} in ({})'.format(
                self.kind,
                self.key,
                ','.join(['%s'] * len(keys))
            )
            as_list = 1

        if not keys:
            if as_list:
                return []
            else:
                return None

        rows = self.db(cmd, *keys)

        if as_list:
            return Result(rows, self)

        for rec in Result(rows, self):
            return rec

    def get_attributes(self):
        """
        get complete set of attributes for the record type

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> sam = Person(**{'name': 'Sam', 'age':15})
        >>> sorted(sam.keys())
        ['age', 'name']
        >>> id = people.put(sam)
        >>> people.get_attributes()
        ['name', 'age', 'kids', 'birthdate']

        """
        cmd = 'select * from %s where 1=2' % self.kind
        rows = self.db(cmd)
        return [rec[0] for rec in rows.cursor.description if rec[0] != 'id']

    def _delete(self, ids):
        if ids:
            affected = list(self.get(ids))

            for rec in affected:
                self.before_delete(rec)

            spots = ','.join('%s' for _ in ids)
            cmd = 'delete from {} where {} in ({})'.format(
                self.kind, self.key, spots)
            self.db(cmd, *ids)

            for rec in affected:
                self.after_delete(rec)

            return ids

    def delete(self, *args, **kwargs):
        """
        delete a record

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sally', age=25))
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Joe', age=25))
        >>> joe = people.get(id)
        >>> id
        3
        >>> bool(joe)
        True

        >>> joe
        <Person {'name': 'Joe', 'age': 25, 'kids': None, 'birthdate': None}>
        >>> people.delete(id)
        [3]

        >>> joe = people.get(id)
        >>> joe
        >>> bool(joe)
        False

        >>> bool(people.find(name='Sally'))
        True
        >>> people.delete(name='Sallie')
        >>> bool(people.find(name='Sally'))
        True
        >>> people.delete()
        >>> people.delete(name='Sally')
        [1]
        >>> bool(people.find(name='Sally'))
        False

        """
        ids = []
        for key in args:
            if hasattr(key, 'get'):
                key = key.get(self.id_name)
            ids.append(key)
        if kwargs:
            ids.extend(self._find(**kwargs))
        return self._delete(ids)

    def exists(self, keys=None):
        """
        tests for existence of a record

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sally', age=25))
        >>> id
        1
        >>> sally = people.get(id)
        >>> sally
        <Person {'name': 'Sally', 'age': 25, 'kids': None, 'birthdate': None}>
        >>> people.exists(1)
        True
        >>> people.exists(2)
        False
        >>> people.exists([1, 2])
        [True, False]
        >>> id = people.put(Person(name='Sam', age=25))
        >>> people.exists([1, 2])
        [True, True]

        """

        if not isinstance(keys, (list, tuple)):
            keys = (keys,)
        slots = (','.join(['%s']*len(keys)))
        cmd = 'select distinct %s from %s where %s in (%s)' % (
            self.key, self.kind, self.key, slots)
        rows = self.db(cmd, *keys)

        found_keys = [rec[0] for rec in rows]
        if len(keys) > 1:
            result = [(key in found_keys) for key in keys]
        else:
            result = keys[0] in found_keys
        return result

    def all(self):
        """
        Retrieves all entities

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sally', age=25))
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Joe', age=25))
        >>> people.all()[0]
        <Person {'name': 'Sally', 'age': 25, 'kids': None, 'birthdate': None}>

        """
        return RecordList(self)

    def zap(self):
        """
        deletes all entities of the given kind

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sally', age=25))
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Joe', age=25))
        >>> len(people.all())
        3

        >>> people.zap()
        >>> people.all()
        []

        """
        cmd = 'delete from ' + self.kind
        self.db(cmd)

    def __len__(self):
        """
        returns number of entities

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> len(people)
        0
        >>> id = people.put(Person(name='Sam', age=15))
        >>> id = people.put(Person(name='Sally', age=25))
        >>> len(people)
        2

        """
        cmd = 'select count(*) cnt from ' + self.kind
        return int(self.db(cmd).cursor.fetchone()[0])

    def _find(self, **kwargs):
        """
        Find keys that meet search critieria
        """
        items = kwargs.items()
        clause = ' and '.join('`%s`=%s' % (k, '%s') for k, v in items)
        cmd = ' '.join([
            'select distinct',
            self.key,
            'from',
            self.kind,
            'where',
            clause,
        ])
        result = self.db(cmd, *[v for _, v in items])
        return [i[0] for i in result]

    def find(self, **kwargs):
        """
        finds entities that meet search criteria

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Sally', age=55))
        >>> id = people.put(Person(name='Bob', age=25))

        >>> print(people.find(age=25))
        person
        _id name age kids birthdate
        --- ---- --- ---- ---------
          1 Sam   25 None None
          3 Bob   25 None None
        2 person records

        >>> people.find(name='Sam')
        [<Person {'name': 'Sam', 'age': 25, 'kids': None, 'birthdate': None}>]
        >>> len(people.find(name='Sam'))
        1

        """
        items = kwargs.items()
        where_clause = ' and '.join('`%s`=%s' % (k, '%s') for k, v in items)
        order_by = self.order_by and (' order by ' + self.order_by) or ''
        cmd = 'select * from ' + self.kind + ' where ' + where_clause + order_by
        result = self.db(cmd, *[v for _, v in items])
        return Result(result, self)

    def first(self, **kwargs):
        """
        finds the first record that meet search criteria

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Sally', age=55))
        >>> id = people.put(Person(name='Bob', age=25))
        >>> people.first(age=5)
        >>> people.first(age=25)
        <Person {'name': 'Sam', 'age': 25, 'kids': None, 'birthdate': None}>

        """
        for item in self.find(**kwargs):
            return item

    def last(self, **kwargs):
        """
        finds the last record that meet search criteria

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Sally', age=55))
        >>> id = people.put(Person(name='Bob', age=25))
        >>> people.last(age=5)
        >>> people.last(age=25)
        <Person {'name': 'Bob', 'age': 25, 'kids': None, 'birthdate': None}>

        """
        rows = self._find(**kwargs)
        if rows:
            return self.get(rows[-1])
        return None

    def search(self, text):
        """
        search for records that match text

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam Adam Jones', age=25))
        >>> id = people.put(Person(name='Sally Mary Smith', age=55))
        >>> id = people.put(Person(name='Bob Marvin Smith', age=25))

        >>> list(people.search('bo smi'))
        [<Person {'name': 'Bob Marvin Smith', 'age': 25, 'kids': None, 'birthdate': None}>]

        >>> list(people.search('smi 55'))
        [<Person {'name': 'Sally Mary Smith', 'age': 55, 'kids': None, 'birthdate': None}>]

        """
        def matches(item, terms):
            """returns True if an item matches the given search terms"""
            values = [
                str(v).lower() for k, v in item.items()
                if not k.startswith('_')
            ]
            return all(any(t in s for s in values) for t in terms)

        search_terms = list(set([i.lower() for i in text.strip().split()]))
        for rec in self:
            if matches(rec, search_terms):
                yield rec

    def filter(self, function):
        """
        finds records that satisfiy filter

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam Adam Jones', age=25))
        >>> id = people.put(Person(name='Sally Mary Smith', age=55))
        >>> id = people.put(Person(name='Bob Marvin Smith', age=25))
        >>> list(people.filter(lambda a: 'Mary' in a.name))
        [<Person {'name': 'Sally Mary Smith', 'age': 55, 'kids': None, 'birthdate': None}>]

        """
        for rec in self:
            if function(rec):
                yield rec

    def __iter__(self):
        """
        interates through records

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Sally', age=55))
        >>> id = people.put(Person(name='Bob', age=25))
        """
        """
        >>> for rec in people: print(rec)

        Person
          name ................: 'Sam'
          age .................: 25
        Person
          name ................: 'Sally'
          age .................: 55
        Person
          name ................: 'Bob'
          age .................: 25
        >>> sum(person.age for person in people)
        105

        """
        order_by = self.order_by and (' order by ' + self.order_by) or ''
        cmd = 'select * from ' + self.kind + order_by
        rows = self.db(cmd)
        return get_result_iterator(rows, self)

    def __getitem__(self, key):
        """
        return records or slices of records by position

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id1 = people.put(Person(name='Sam', age=25))
        >>> id2 = people.put(Person(name='Sally', age=55))
        >>> id3 = people.put(Person(name='Bob', age=25))

        >>> people[0]
        <Person {'name': 'Sam', 'age': 25, 'kids': None, 'birthdate': None}>

        >>> people[1]
        <Person {'name': 'Sally', 'age': 55, 'kids': None, 'birthdate': None}>

        >>> people[-1]
        <Person {'name': 'Bob', 'age': 25, 'kids': None, 'birthdate': None}>

        >>> people[0:2]
        [<Person {'name': 'Sam', 'age': 25, 'kids': None, 'birthdate': None}>, <Person {'name': 'Sally', 'age': 55, 'kids': None, 'birthdate': None}>]

        >>> people[::2]
        [<Person {'name': 'Sam', 'age': 25, 'kids': None, 'birthdate': None}>, <Person {'name': 'Bob', 'age': 25, 'kids': None, 'birthdate': None}>]

        >>> people[::-2]
        [<Person {'name': 'Bob', 'age': 25, 'kids': None, 'birthdate': None}>, <Person {'name': 'Sam', 'age': 25, 'kids': None, 'birthdate': None}>]

        >>> people[1:-1]
        [<Person {'name': 'Sally', 'age': 55, 'kids': None, 'birthdate': None}>]

        >>> try:
        ...     people[3]
        ... except IndexError as e:
        ...     print(e)
        Index (3) out of range

        """
        n = len(self)
        if isinstance(key, slice):
            # get the start, stop, and step from the slice
            start, stop, step = key.indices(n)
            return [self[ii] for ii in range(start, stop, step)]
        elif isinstance(key, int):
            if key < 0:
                key += n
            elif key >= n:
                raise IndexError('Index ({}) out of range'.format(key))
            cmd = ' '.join([
                'select distinct',
                self.key,
                'from',
                self.kind,
                'limit %s,1'
                ]) % (key)
            rs = list(self.db(cmd))
            if rs:
                return self.get(list(rs)[0][0])
            else:
                return 'no records'
        else:
            raise TypeError('Invalid argument type')

    def __str__(self):
        """
        format for humans

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Sally', age=55))
        >>> id = people.put(Person(name='Bob', age=25))
        >>> print(people)
        person
        _id name  age kids birthdate
        --- ----- --- ---- ---------
          1 Sam    25 None None
          2 Sally  55 None None
          3 Bob    25 None None
        3 person records

        >>> people.zap()
        >>> print(people)
        Empty list

        """
        return str(self.all())

    def __repr__(self):
        """
        unabiguous representation

        >>> db = gitdata.database.setup_test()
        >>> class Person(Record): pass
        >>> class People(RecordStore): pass
        >>> people = People(db, Person)
        >>> id = people.put(Person(name='Sam', age=25))
        >>> id = people.put(Person(name='Sally', age=55))
        >>> id = people.put(Person(name='Bob', age=25))
        >>> repr(people)
        '<RecordStore(Person)>'
        >>> people.zap()
        >>> people
        <RecordStore(Person)>
        >>> len(people)
        0

        """
        return '<RecordStore({})>'.format(self.record_class.__name__)


def table_of(klass, db=None, name=None, key='id'):
    """Return a table of Records of the given class

    The klass parameter can be a subclass of gitdata.Model or
    a table name.  If a gitdata.Model is provided the actual
    table name is derived from the class name.  If the table
    name is provivded then it's taken as-is.

    Uses the current database if none is provided.

    >>> db = gitdata.database.setup_test()

    >>> people = table_of('person', db)
    >>> id = people.put(dict(name='Sam', age=20))
    >>> person = people.first(name='Sam')
    >>> person['age']
    20
    """
    db = db or gitdata.database.connect()
    if isinstance(klass, str):
        return RecordStore(db, name=name or klass, key=key)
    else:
        return RecordStore(db, klass, name=name, key=key)
