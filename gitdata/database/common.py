# -*- coding: utf-8 -*-

"""
    gitdata.database

    A database module that does less.
"""

import collections
import inspect
import logging
import os
import timeit
import warnings
# from decimal import Decimal

# from gitdata.utils import obfuscate
from gitdata.utils import ItemList, Bunch


__all__ = [
    'Database',
    'UnknownDatabaseException',
    'DatabaseException',
    'EmptyDatabaseException',
    'Result',
]


warnings.filterwarnings("ignore", "Unknown table.*")

ARRAY_SIZE = 1000

ERROR_TPL = """
  statement: {!r}
  parameters: {}
  message: {}
"""

class UnknownDatabaseException(Exception):
    """exception raised when the database is unknown"""


class DatabaseException(Exception):
    """exception raised when a database server error occurs"""


class EmptyDatabaseException(Exception):
    """exception raised when a database is empty"""


class Result(object):
    """database query result"""
    # pylint: disable=too-few-public-methods

    def __init__(self, cursor, array_size=ARRAY_SIZE):
        self.cursor = cursor
        self.array_size = array_size

    def __iter__(self):
        while True:
            results = self.cursor.fetchmany(self.array_size)
            if not results:
                break
            for result in results:
                yield result

    def __len__(self):
        # deprecate? - not supported by all databases
        count = self.cursor.rowcount
        return count if count > 0 else 0

    def __str__(self):
        """nice for humans"""
        labels = list(map(lambda a: '{0}'.format(*a), self.cursor.description))
        return str(ItemList(self, labels=labels))

    def __repr__(self):
        """useful and unambiguous"""
        return repr(list(self))

    def first(self):
        """return first item in result"""
        for i in self:
            return i


class Database:
    """
    Database

    A Database wraps the standard Python db API and provides additional
    uniformity and support for basic SQL to make it more convenient to
    do common things most apps need to do with databases.
    """

    paramstyle = 'pyformat'
    stats = []  # make this a class attribute to catch across instances
    debug = False  # make this a class attribute to catch across instances

    def __init__(self, factory, *args, **keywords):
        """Initialize with factory method to generate DB connection
        (e.g. odbc.odbc, cx_Oracle.connect) plus any positional and/or
        keyword arguments required when factory is called."""
        self.__connection = None
        self.__factory = factory
        self.__args = args
        self.__keywords = keywords
        self.log = []
        self.rowcount = None
        self.lastrowid = None

    def __getattr__(self, name):
        if self.__connection is None:
            self.__connection = self.__factory(*self.__args, **self.__keywords)
            logger = logging.getLogger(__name__)
            logger.debug('opening %s', self.__class__.__name__)
        return getattr(self.__connection, name)

    def translate(self, command, *args, many=False):
        """translate sql dialects

        The Python db API standard does not attempt to unify parameter passing
        styles for SQL arguments.  This translate routine attempts to do that
        for each database type.  For databases that use the preferred pyformat
        paramstyle nothing needs to be done.  Databases requiring other
        paramstyles should override this method to translate the command
        to the required style.
        """
        def issequenceform(obj):
            """test for a sequence type that is not a string"""
            if isinstance(obj, str):
                return False
            return isinstance(obj, collections.Sequence)

        if self.paramstyle == 'qmark':
            if not many and len(args) == 1 and hasattr(args[0], 'items') and args[0]:
                # a dict-like thing
                placeholders = {key: ':%s' % key for key in args[0]}
                cmd = command % placeholders, args[0]
            elif many and len(args) >= 1 and hasattr(args[0], 'items') and args[0]:
                # a dict-like thing
                placeholders = {key: ':%s' % key for key in args[0]}
                cmd = command % placeholders, args
            elif len(args) >= 1 and issequenceform(args[0]):
                # a list of tuple-like things
                placeholders = ['?'] * len(args[0])
                cmd = command % tuple(placeholders), args
            else:
                # just one tuple-like thing
                placeholders = ['?'] * len(args)
                cmd = command % tuple(placeholders), args
            return cmd

        elif self.paramstyle == 'named':
            if not many and len(args) == 1 and hasattr(args[0], 'items'):
                # a dict-like thing
                placeholders = {key: ':%s' % key for key in args[0]}
                cmd = command % placeholders, args[0]
            elif many and len(args) >= 1 and hasattr(args[0], 'items'):
                # a dict-like thing
                placeholders = {key: ':%s' % key for key in args[0]}
                cmd = command % placeholders, args
            elif len(args) >= 1 and issequenceform(args[0]):
                # a list of tuple-like things
                placeholders = [':%d' % (n+1) for n in range(len(args[0]))]
                cmd = command % tuple(placeholders), args[0]
            else:
                # just one tuple-like thing
                placeholders = [':%d' % (n+1) for n in range(len(args))]
                cmd = command % tuple(placeholders), args
            return cmd

        else:
            params = not many and \
                len(args) == 1 and \
                hasattr(args[0], 'items') and \
                args[0] or \
                args
            return command, params

    def _execute(self, cursor, method, command, *args):
        """execute the SQL command"""

        def format_stack(stack):  # pragma:  no cover
            n = m = 0
            for n, item in enumerate(stack):
                if item[3] == 'run_app':
                    break
            for m, item in enumerate(stack):
                if not item[1].endswith('database.py'):
                    break
            return '<pre><small>{}</small></pre>'.format(
                '<br>'.join('{3} : line {2} in {1}'.format(
                    *rec
                ) for rec in stack[m:n])
            )

        start = timeit.default_timer()
        many = method == cursor.executemany
        command, params = self.translate(command, *args, many=many)
        try:
            method(command, params)
        except Exception as error:
            raise DatabaseException(ERROR_TPL.format(command, args, error)) from error
        else:
            self.rowcount = cursor.rowcount
        finally:
            if self.debug:
                elapsed = timeit.default_timer() - start
                self.log.append('  SQL ({:5.1f} ms): {!r} - {!r}'.format(
                    elapsed * 1000,
                    command,
                    args,
                ))
                source = format_stack(inspect.stack())
                type(self).stats.append(
                    (elapsed, repr(command), repr(args), source)
                )

        if cursor.description:
            return Result(cursor)
        else:
            self.lastrowid = getattr(cursor, 'lastrowid', None)
            return self.lastrowid or None

    def execute(self, command, *args):
        """execute a SQL command with optional parameters"""
        cursor = self.cursor()
        return self._execute(cursor, cursor.execute, command, *args)

    def execute_many(self, command, sequence):
        """execute a SQL command with a sequence of parameters"""
        if not sequence:
            return None
        cursor = self.cursor()
        return self._execute(cursor, cursor.executemany, command, *sequence)

    def __call__(self, command, *args):
        return self.execute(command, *args)

    def runs(self, sql, *args, **kwargs):
        """
        Run multiple SQL statements from a string

        The SQL statements in the soure string must be separated by a newline
        followed by a semicolon (i.e. '\\n;').

        """

        def split(statements):
            """split the sql statements"""
            return list(filter(bool, map(str.strip, statements.split(';\n'))))

        logger = logging.getLogger(__name__)

        statements = split(sql)

        logger.debug('running %s SQL statements', len(statements))

        for statement in statements:
            self(statement, *args, **kwargs)

        logger.debug('ran %s SQL statements', len(statements))


    def run(self, filename, *args, **kwargs):
        """Run multiple SQL statements from a file

        The SQL statements in the soure file must be separated by a newline
        followed by a semicolon (i.e. '\n;').

        """

        logger = logging.getLogger(__name__)
        if os.path.isfile(filename):

            logger.debug('running SQL statements from %s', filename)

            with open(filename) as f:
                return self.runs(f.read(), *args, **kwargs)

            logger.debug('ran SQL statements from %s', filename)

        else:
            msg = 'file %s missing' % filename
            logger.error(msg)
            raise DatabaseException(msg)

    def use(self, name):
        """use another database on the same instance"""
        args = list(self.__args)
        keywords = dict(self.__keywords, db=name)
        return type(self)(*args, **keywords)

    def report(self):   # pragma: no cover
        """produce a SQL log report"""
        if self.log:
            return '  Database Queries\n --------------------\n{}\n'.format(
                '\n'.join(self.log))
        return ''

    @classmethod
    def get_stats(cls):
        """Return the stats to the caller, clearing the list of what is returned

            We use a classmethod to support inheritance (over staticmethod)
        """
        result = list(cls.stats)  # get a copy of the list
        del cls.stats[:len(result)]  # clear the list, but more may have been added
        return result

    def get_table_names(self):
        """get list of database tables"""

    @property
    def database(self):
        """Returns an object containing database parameters"""
        return Bunch(
            name=self.__keywords.get('db'),
            host=self.__keywords.get('host'),
            port=self.__keywords.get('port'),
            user=self.__keywords.get('user'),
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        logger = logging.getLogger(__name__)
        logger.debug('closing %s connection',
            self.__class__.__name__)
        self.close()
