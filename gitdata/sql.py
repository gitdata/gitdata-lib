"""
    sql utilities
"""

import inspect
import os

import gitdata
from gitdata.stores.tables import table_of
from gitdata import Record


from gitdata.utils import (
    RecordList, load
)


def get_result_iterator(rows, kind, store=None):
    """returns an iterator that iterates over the rows and zips the names onto
    the items being iterated so they come back as dicts"""
    names = [d[0] == 'id' and '_id' or d[0] for d in rows.cursor.description]
    set_store = dict(__store=store) if store else {}
    for rec in rows:
        yield kind(
            ((k, v) for k, v in zip(names, rec)),
            **set_store
        )


class Result(object):
    """rows resulting from a method call"""
    # pylint: disable=too-few-public-methods

    def __init__(self, rows, kind, name=None):
        self.rows = rows
        self.kind = kind
        self.name = name

    def __iter__(self):
        store = gitdata.table_of(self.kind, name=self.name) if self.name else None
        return get_result_iterator(self.rows, self.kind, store)

    # def __len__(self):
    #     return self.rows.cursor.rowcount

    def __repr__(self):
        return repr(list(self))

    def __str__(self):
        return str(RecordList(self))


class SqlExpression:

    def __init__(self, *terms):
        self.terms = terms

    def __str__(self):
        return ' '.join(str(t) for t in self.terms)

    def __and__(self, value):
        return SqlExpression(self, 'and', str(value))

    def __or__(self, value):
        return SqlExpression(self, 'or', str(value))


class SqlTerm:

    def __init__(self, name):
        self.name = name
        print(name)

    def __str__(self):
        return '`{}`'.format(self.name)

    def __eq__(self, value):
        return SqlExpression(str(self), '=', repr(value))

    def __ne__(self, value):
        return SqlExpression(str(self), '!=', repr(value))

    def __gt__(self, value):
        return SqlExpression(str(self), '>', repr(value))

    def __ge__(self, value):
        return SqlExpression(str(self), '>=', repr(value))

    def __lt__(self, value):
        return SqlExpression(str(self), '<', repr(value))

    def __le__(self, value):
        return SqlExpression(str(self), '<=', repr(value))


# class SqlTable:

#     def __init__(self, db, table_name, kind=Record):
#         self.db = db
#         self.table_name = table_name
#         self.kind = kind

#     def __iter__(self):
#         for row in gitdata.table_of(self.kind, name=self.table_name, db=self.db):
#             yield row

#     def __call__(self, *args):
#         columns = ', '.join(a for a in args if not isinstance(a, SqlExpression))
#         clauses = ' and '.join(
#             str(a) for a in args if isinstance(a, SqlExpression)
#         )
#         if clauses:
#             clauses = ' where ' + clauses
#         cmd = 'select %s from %s%s' % (columns, self.table_name, clauses)
#         for row in Result(self.db(cmd), self.kind):
#             yield row

#     def __len__(self):
#         cmd = f'select count(*) from {self.table_name}'
#         return list(self.db(cmd))[0][0]

#     def select(
#             self, *args,
#             where=None, group_by=None, order_by=None, limit=None
#         ):
#         columns = ', '.join(args)
#         cmd = [
#             'select %s from %s' % (columns, self.table_name)
#         ]
#         if where:
#             cmd.append('where ', where)
#         if group_by:
#             cmd.append('group by ', group_by)
#         if order_by:
#             cmd.append('order by ', order_by)
#         if limit:
#             cmd.append('limit ', limit)
#         for row in Result(self.db(cmd), self.kind):
#             yield row

#     def __getattr__(self, name):
#         return SqlTerm(name)

#     def get(self, ids):
#         cmd = f'select * from {self.table_name} where id in %s'
#         as_list = True
#         if isinstance(ids, (int, str)):
#             ids = list(map(int, [ids]))
#             as_list = False
#         rows = Result(self.db(cmd, ids), self.kind)
#         if as_list:
#             return rows
#         else:
#             if rows:
#                 return list(rows)[0]

#     def __getitem__(self, key):
#         return self.get(key)

#     def __str__(self):
#         return str(gitdata.table_of(self.kind, name=self.table_name, db=self.db))


class SqlQuery:

    def __init__(self, db, pathname):
        self.db = db
        self.pathname = pathname
        self.kind = Record

    def __call__(self, *args, **kwargs):
        code = load(self.pathname)
        return Result(self.db(code, *args or kwargs), self.kind)

    def __iter__(self):
        for row in self():
            yield row

    # def to(self, kind):
    #     for item in self:
    #         return kind(item)

    # def execute(self, *args, **kwargs):
    #     code = load(self.pathname)
    #     cursor = self.db.cursor()
    #     result = cursor.execute(code, *args or kwargs)
    #     return result

    # def __str__(self):
    #     return str(self())


class SQL:
    """SQL Class

    The SQL class provides a convenient way to work with SQL databases.  It
    provides access to database tables and can load and execute SQL queries
    stored in .sql files by referring to the name of the file.  Parameters
    can be passed to SQL queries as required by treating the attribute as
    a callable attribute.
    """

    def __init__(self, db, path='sql'):
        self.db = db
        if os.path.isfile(path):
            dirname = os.path.dirname(path)
        elif os.path.isdir(path):
            dirname = path
        else:
            raise Exception(f'{path} is not a directory or filename')

        if os.path.isdir(os.path.join(dirname, 'sql')):
            path = os.path.join(dirname, 'sql')
        else:
            path = dirname

        self.path = os.path.realpath(path)

    def __getattr__(self, name):
        pathname = os.path.join(self.path, name + '.sql')

        if os.path.isfile(pathname):
            return SqlQuery(self.db, pathname)

        elif name in self.db.table_names:
            return table_of(Record, name=name, db=self.db)


def get_sql(path=None, db=None):
    """Return a SQL object"""

    path = path or os.path.abspath((inspect.stack()[1])[1])

    db = db or gitdata.database.connect()
    return SQL(db, path)
