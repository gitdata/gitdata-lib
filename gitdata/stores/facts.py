"""
    gitdata fact store
"""

import io
import os
import sqlite3

import gitdata
import gitdata.buckets
from .common import fixval, get_type_str, AbstractStore, entify, retype

valid_types = [
    'str', 'bytes', 'int', 'float', 'decimal.Decimal',
    'datetime.date', 'datetime.datetime', 'bool', 'NoneType',
]

insert = (
    'insert into facts ('
    '    entity, attribute, value_type, value'
    ') values (?, ?, ?, ?)'
)

delete = (
    'delete from facts where '
    '    entity=? and attribute=? and value=?'
)


def get_db(connection):
    def query(cmd, *args, **kwargs):
        cursor = connection.cursor()
        cursor.execute(cmd, *args, **kwargs)
        return cursor.fetchall()
    return query


class Sqlite3FactStore(AbstractStore):
    """Sqlite3 based Entity Store"""

    def __init__(self, database, *args, new_uid=gitdata.utils.new_uid, **kwargs):
        self.database = database
        self.new_uid = new_uid
        self.connection = sqlite3.Connection(database, *args, **kwargs)
        if database == ':memory:':
            self.bucket = gitdata.buckets.MemoryBucket(id_factory=new_uid)
        else:
            path = os.path.join(os.path.dirname(database or '.'), 'blobs')
            self.bucket = gitdata.buckets.FileBucket(path, id_factory=new_uid)

    def setup(self):
        """Set up the persistent data store"""
        sql = """
        drop table if exists `facts`;
        create table if not exists `facts` (
            `entity` char(32) not null,
            `attribute` varchar(100) not null,
            `value_type` varchar(30) not null,
            `value` mediumtext not null
        );
        """

        with self.connection:
            cursor = self.connection.cursor()
            commands = list(filter(bool, sql.split(';\n')))
            for command in commands:
                cursor.execute(command)

    def add(self, facts):
        """add facts"""
        records = []
        for entity, attribute, value in facts:
            if value is not None:
                if isinstance(value, io.BytesIO):
                    value = self.bucket.puts(value)
                value_type = get_type_str(value)
                if value_type in valid_types:
                    records.append((entity, attribute, value_type, value))
                else:
                    msg = 'unsupported type <type %s> in value %r'
                    raise Exception(msg % (value_type, value))

        with self.connection:
            cursor = self.connection.cursor()
            cursor.executemany(insert, records)

    def remove(self, facts):
        """remove facts"""
        records = facts
        with self.connection:
            cursor = self.connection.cursor()
            cursor.executemany(delete, records)

    def matching(self, pattern=(None, None, None)):
        """Return facts matching pattern"""

        sub, pred, obj = pattern

        spn = 'select value, value_type from facts where entity=? and attribute=?'
        sno = 'select attribute from facts where entity=? and value=?'
        snn = 'select attribute, value, value_type from facts where entity=?'
        npo = 'select entity from facts where attribute=? and value=?'
        npn = 'select entity, value, value_type from facts where attribute=?'
        nno = 'select entity, attribute from facts where value=?'
        nnn = 'select entity, attribute, value, value_type from facts'

        with self.connection:
            cursor = self.connection.cursor()
            db = cursor.execute

            db = get_db(self.connection)
            if sub != None:
                if pred != None:
                    q = [retype(*a) for a in db(spn, (sub, pred))]
                    # subj pred obj
                    if obj != None:
                        if obj in q:
                            yield (sub, pred, obj)
                    # subj pred None
                    else:
                        for r in q:
                            yield (sub, pred, r)
                else:
                    # subj None obj
                    if obj != None:
                        q = [a[0] for a in db(sno, (sub, obj))]
                        for r in q:
                            yield (sub, r, obj)
                    # sub None None
                    else:
                        q = db(snn, (sub,))
                        for r, value, value_type in q:
                            yield (sub, r, retype(value, value_type))
            else:
                if pred != None:
                    # None pred obj
                    if obj != None:
                        q = db(npo, (pred, obj))
                        for s, in q:
                            yield (s, pred, obj)
                    # None pred None
                    else:
                        q = db(npn, (pred,))
                        for r, value, value_type in q:
                            yield (r, pred, retype(value, value_type))
                else:
                    # None None obj
                    if obj != None:
                        q = [(row_id, attribute) for row_id, attribute in db(nno, (obj,))]
                        for r, s in q:
                            yield (r, s, obj)
                    # None None None
                    else:
                        # q = [(row_id, attribute, value, value_type) for row_id, attribute, value in db(nnn)]
                        q = db(nnn)
                        for r, s, value, value_type in q:
                            yield (r, s, retype(value, value_type))

    def put(self, entity):
        """stores an entity"""

        def bucketize(v):
            if isinstance(v, io.BytesIO):
                return self.bucket.puts(v)
            return v

        keys = [k.lower() for k in entity.keys()]
        values = [bucketize(entity[k]) for k in keys]
        value_types = [get_type_str(v) for v in values]
        values = [fixval(i) for i in values]  # same fix as above

        for n, atype in enumerate(value_types):
            if atype not in valid_types:
                msg = 'unsupported type <type %s> in value %r'
                raise Exception(msg % (atype, keys[n]))

        uid = entity.get('uid', gitdata.utils.new_uid())

        n = len(keys)
        param_list = list(zip([uid]*n, keys, value_types, values))
        with self.connection:
            cursor = self.connection.cursor()
            cursor.executemany(insert, param_list)

        return uid

    def get(self, uid):
        """get an entity from the entity store"""
        def unbucketize(fact):
            s, p, t, o = fact
            return s, p, t, self.bucket.gets(o, o)
        select = 'select * from facts where entity=?'
        cursor = self.connection.cursor()
        cursor.execute(select, (uid,))
        facts = list(map(unbucketize, cursor.fetchall()))
        result = entify(facts)
        return result

    def delete(self, uid):
        """delete an entity from the fact store"""
        select = 'delete from facts where entity=?'
        with self.connection:
            cursor = self.connection.cursor()
            cursor.execute(select, (uid,))

    def clear(self):
        """delete all facts"""
        self.bucket.clear()
        with self.connection as connection:
            cursor = connection.cursor()
            cursor.execute('delete from facts')

    def __len__(self):
        """return the number of facts stored"""
        cursor = self.connection.cursor()
        cursor.execute('select count(*) from facts')
        result = list(cursor.fetchall())[0][0]
        return result


class MemoryFactStore(AbstractStore):
    """Memory based fact store"""

    facts = []

    def __init__(self, new_uid=gitdata.utils.new_uid):
        self.new_uid = new_uid

    def setup(self):
        """Setup persistent store"""
        self.facts = []

    def add(self, facts):
        self.facts.extend(
            filter(lambda a: a[-1] is not None, facts)
        )

    def remove(self, facts):
        for fact in facts:
            if fact in self.facts:
                self.facts.remove(fact)

    def put(self, entity):
        """store an entity"""
        uid = entity.get('uid', self.new_uid())
        facts = ((uid, attribute, value) for attribute, value in entity.items())
        self.add(facts)
        return uid

    def get(self, uid):
        """get an entity"""
        result = {}
        for entity, attribute, value in self.facts:
            if entity == uid:
                result[attribute] = value
        return result or None

    def delete(self, uid):
        """delete all facts for an entity"""
        self.facts[:] = (fact for fact in self.facts if fact[0] != uid)

    def clear(self):
        """clear the fact store"""
        self.facts = []

    def matching(self, pattern=(None, None, None)):
        """Return facts matching pattern"""

        sub, pred, obj = pattern

        data = [
            (entity, attribute, value)
            for (entity, attribute, value) in self.facts
            if (
                (sub is None or sub == entity) and
                (pred is None or pred == attribute) and
                (obj is None or obj == value)
            )
        ]
        return data

    def __len__(self):
        """return the number of facts stored"""
        return len(self.facts)

FactStore = MemoryFactStore


def facts_of(location, new_uid=gitdata.utils.new_uid):
    """Return a fact store for a location"""
    if location == ':memory:' or location is None:
        return MemoryFactStore(new_uid=new_uid)
    if os.path.isdir(location):
        return Sqlite3FactStore(
            os.path.join(location, 'facts'), new_uid=new_uid
        )
    raise Exception('fatal: not a GitData respository')
