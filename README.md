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

The same two commands work across CSV files, SQLite databases,
MariaDB/MySQL databases, and Oracle databases:

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
references. GitData reads `PASSWORD` by default:

```bash
export PASSWORD='your-password'

SERVER='mysql://user@db.example.com'
DATABASE='mysql://user@db.example.com/sales'
TABLE='mysql://user@db.example.com/sales.orders'
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
Inline passwords, query parameters, and fragment selectors are not accepted.
To use a password variable other than `PASSWORD`, set `GITDATA_PASSWORD_ENV`
to its name:

```bash
export GITDATA_PASSWORD_ENV=MYSQL_PASSWORD
export MYSQL_PASSWORD='your-password'
```

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

export GITDATA_PASSWORD_ENV=GITDATA_EXAMPLE_PASSWORD
export GITDATA_EXAMPLE_PASSWORD=example
gitdata ls 'mysql://root@127.0.0.1:3307/gitdata_example'
gitdata scan --limit 5 'mysql://root@127.0.0.1:3307/gitdata_example.customers'
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

## Oracle

Install the optional Oracle driver, then set the password. GitData reads
`PASSWORD` by default:

```bash
python3 -m pip install 'gitdata-lib[oracle]'
export PASSWORD='your-password'

CONNECTION='oracle://app@db.example.com/FREEPDB1'
SCHEMA="${CONNECTION}/APP"
TABLE="${SCHEMA}/orders"
```

Explore the service, visible schemas, and their tables with the same commands:

```bash
# List schemas containing tables visible to the connected user
gitdata ls "$CONNECTION"

# Show visible-schema table and estimated-row counts
gitdata ls -l "$CONNECTION"

# List tables visible in one schema
gitdata ls "$SCHEMA"

# Show table column and estimated-row counts; size may be unavailable
gitdata ls -l "$SCHEMA"

# Show column details
gitdata ls -l "$TABLE"

# Preview rows
gitdata scan --limit 10 "$TABLE"
```

Oracle service-name references follow these shapes; port `1521` may be omitted:

```text
oracle://user@host
oracle://user@host:port/service
oracle://user@host:port/service/schema
oracle://user@host:port/service/schema/table
```

When the service is omitted, GitData first tries the username as the service
name. If Oracle does not advertise that service, GitData asks for an explicit
`/service` path.

Some Oracle installations expose a connection target by SID rather than by a
registered service name. Use the explicit `oracle+sid` scheme in that case:

```text
oracle+sid://user@host/SID
oracle+sid://user@host:port/SID/schema
oracle+sid://user@host:port/SID/schema/table
```

Unlike a service-name reference, a SID reference always requires the `/SID`
path. GitData passes it to `oracledb.makedsn(..., sid=...)`; it does not enable
Oracle Thick mode.

Some Oracle databases accept connections only through Oracle Client libraries
(`python-oracledb` Thick mode). Use the canonical `+thick` schemes:

```text
oracle+thick://user@host/service
oracle+sid+thick://user@host/SID
```

Thick/Thin mode is process-global in `python-oracledb` and cannot be changed
after the first Oracle connection or pool. A `+thick` reference initializes
Thick mode and therefore must be used before any Thin connection in that
process. If Thin mode is already active, restart GitData and use the `+thick`
reference first. Once Thick mode is active, later `oracle://` and
`oracle+sid://` references also use Thick mode; those plain schemes mean only
that the reference does not request Thick initialization. Install Oracle
Client libraries and configure the operating system loader so
`oracledb.init_oracle_client()` can find them before GitData starts.

To use a password variable other than `PASSWORD`, set
`GITDATA_PASSWORD_ENV` to its name:

```bash
export GITDATA_PASSWORD_ENV=ORACLE_PASSWORD
export ORACLE_PASSWORD='your-password'
```

Inline passwords, query parameters, and fragment selectors are not accepted.
After connecting, GitData uses Oracle's permission-aware `ALL_*` dictionary
views: the connection root lists schemas containing tables visible to the user,
and a schema path lists its visible tables. Table references must include the
schema segment; the earlier `/service/table` shorthand is not supported.
Ordinary Oracle schema, table, and column names are shown in lowercase. Quoted
identifiers are shown with their double quotes so names that differ only by
Oracle quoting remain distinct; use the displayed spelling as the corresponding
path component (the quotes may be URL-encoded as `%22`).
