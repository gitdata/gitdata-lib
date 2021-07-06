"""
    gitdata database
"""

from .common import Database
from .sqlite3 import Sqlite3Database, setup_test
from .mysql import MySQLDatabase


class UnknownDatabaseException(Exception):
    """Unknown Database Exception"""


def connect(engine='sqlite3', **kwargs):
    """Returns a Database object

    >>> db = connect()
    >>> db('drop table if exists person')
    >>> db(\"\"\"
    ...     create table if not exists person (
    ...     id integer primary key autoincrement,
    ...     name      varchar(100),
    ...     age       smallint,
    ...     kids      smallint,
    ...     birthdate date,
    ...     salary    decimal(8,2)
    ...     )
    ... \"\"\")

    >>> db("insert into person (name, age) values ('Joe', 32)")
    1

    >>> db('select * from person')
    [(1, 'Joe', 32, None, None, None)]

    >>> print(db('select * from person'))
    id name age kids birthdate salary
    -- ---- --- ---- --------- ------
     1 Joe   32 None None      None

    >>> create_person_table = \"\"\"
    ...     create table if not exists person (
    ...     id integer primary key autoincrement,
    ...     name      varchar(100),
    ...     age       smallint,
    ...     kids      smallint,
    ...     birthdate date,
    ...     salary    decimal(8,2)
    ...     )
    ... \"\"\"
    >>> insert_person = "insert into person (name, age) values (%s, %s)"
    >>> with connect(database=':memory:') as db:
    ...    db(create_person_table)
    ...    db(insert_person, 'Joe', 32)
    ...    db('select * from person')
    1
    [(1, 'Joe', 32, None, None, None)]

    """

    if engine == 'sqlite3':
        return Sqlite3Database(**kwargs)

    elif engine == 'mysql':
        db = MySQLDatabase(**kwargs)
        db.autocommit(1)
        return db

    else:
        raise UnknownDatabaseException
