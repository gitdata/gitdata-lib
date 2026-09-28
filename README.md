# GitData

GitData gives you one set of commands for exploring files and databases.
List what is inside a source with `gitdata ls`, then preview its data with
`gitdata scan`.

## Install

GitData supports Python 3.9 through 3.12.

```bash
python3 -m pip install gitdata-lib
```

Oracle support is optional:

```bash
python3 -m pip install 'gitdata-lib[oracle]'
```

## Explore a data source

The same two commands work across CSV files, SQLite databases, and
MariaDB/MySQL databases:

```bash
gitdata ls <source>
gitdata scan <source>
```

Use `-l` for a detailed listing, `-a` to include system objects, and `--limit`
to choose how many rows to preview.

## CSV

List the columns in a CSV file:

```bash
gitdata ls examples/locations-headered.csv
```

Preview its rows:

```bash
gitdata scan --limit 10 examples/locations-headered.csv
```

## SQLite

Start with the database file, then move into a table or column:

```bash
# List tables
gitdata ls examples/inspection.sqlite

# Show table details
gitdata ls -l examples/inspection.sqlite/customers

# Preview rows
gitdata scan --limit 5 examples/inspection.sqlite/customers

# Examine one column
gitdata scan --limit 5 examples/inspection.sqlite/customers.email
```

SQLite references follow this shape:

```text
path/to/database.sqlite
path/to/database.sqlite/table
path/to/database.sqlite/table.column
```

## MariaDB and MySQL

Keep passwords in environment variables instead of putting them in database
references:

```bash
export GITDATA_DB_PASSWORD='your-password'

SERVER='mysql://user@db.example.com?password_env=GITDATA_DB_PASSWORD'
DATABASE='mysql://user@db.example.com/sales?password_env=GITDATA_DB_PASSWORD'
TABLE='mysql://user@db.example.com/sales.orders?password_env=GITDATA_DB_PASSWORD'
```

Explore the server, database, and table with the same commands:

```bash
# List databases
gitdata ls "$SERVER"

# List tables
gitdata ls "$DATABASE"

# Show columns and indexes
gitdata ls -l "$TABLE"

# Preview rows
gitdata scan --limit 10 "$TABLE"
```

MariaDB/MySQL references follow this shape:

```text
mysql://user@host
mysql://user@host/database
mysql://user@host/database.table
```

If the username is omitted, GitData uses the current operating-system username.
Use `gitdata ls -a` when you also want to see system databases or tables.

### Try the included MariaDB example

The repository includes `examples/mariadb.sql`. Load it into a disposable
MariaDB container:

```bash
docker run --name gitdata-example-mariadb \
  -e MARIADB_ROOT_PASSWORD=example \
  -p 3307:3306 \
  -d mariadb:10.7

until docker exec gitdata-example-mariadb \
  mariadb-admin ping -h 127.0.0.1 -uroot -pexample --silent
do
  sleep 1
done

docker exec -i gitdata-example-mariadb \
  mariadb -uroot -pexample < examples/mariadb.sql

export GITDATA_EXAMPLE_PASSWORD=example
gitdata ls 'mysql://root@127.0.0.1:3307/gitdata_example?password_env=GITDATA_EXAMPLE_PASSWORD'
gitdata scan --limit 5 'mysql://root@127.0.0.1:3307/gitdata_example.customers?password_env=GITDATA_EXAMPLE_PASSWORD'
```

Remove the example when finished:

```bash
docker rm -f gitdata-example-mariadb
```

## Command reference

```text
gitdata ls <source>          list databases, tables, or columns
gitdata ls -l <source>       show a detailed listing
gitdata ls -a <source>       include system objects
gitdata scan <source>        preview and profile data
gitdata scan --limit N ...   preview at most N rows
```

Run a command with `--help` for all options:

```bash
gitdata ls --help
gitdata scan --help
```

## Oracle from Python

Use the optional Oracle driver through the Python API:

```python
import os

from gitdata.database import connect

db = connect(
    'oracle',
    host='127.0.0.1',
    port=1521,
    service_name='FREEPDB1',
    user='app',
    password=os.environ['ORACLE_PASSWORD'],
)

rows = list(db('SELECT 1 FROM dual'))
```
