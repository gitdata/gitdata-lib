# GitData Lib
Data Wrangling for Everyone.

GitData is a fast, scalable, distributed data exploration system
with a rich set of commands that provide ways to gather, manage and query data in an unusually straightforward way.

## Direct inspection

`ls` and `scan` inspect live Connector output directly. They do not initialize a
repository, digest the data into facts, or write to a store.

The repository includes ready-to-use examples. Run these commands from the
repository root:

```bash
# List tables in the SQLite example, list one table's columns, and scan it.
gitdata ls examples/inspection.sqlite
gitdata ls 'examples/inspection.sqlite#customers'
gitdata scan --limit 2 'examples/inspection.sqlite#customers'

# A headered CSV can be inspected in the same way.
gitdata ls examples/locations-headered.csv
gitdata scan --limit 10 examples/locations-headered.csv
```

CSV rows and database query results are traversed lazily. A sampled report marks
cardinality as approximate and reports the number of rows examined as a lower
bound. A complete traversal reports the exact row count.

### MariaDB example

`examples/mariadb.sql` is a `mysqldump` of a `gitdata_example` database with
`customers`, `orders`, and `products` tables. Load it into a disposable MariaDB
container:

```bash
docker run --name gitdata-example-mariadb \
  -e MARIADB_ROOT_PASSWORD=example \
  -p 3307:3306 \
  -d mariadb:10.7@sha256:9a48ac9f196f3d4fd6fea2cab59a49df9e7ca459bf14b2f7b85a0e38a5454571

until docker exec gitdata-example-mariadb \
  mariadb-admin ping -h 127.0.0.1 -uroot -pexample --silent
do
  sleep 1
done

docker exec -i gitdata-example-mariadb \
  mariadb -uroot -pexample < examples/mariadb.sql
```

Keep the password out of the ref by naming an environment variable:

```bash
export GITDATA_EXAMPLE_MARIADB_PASSWORD=example
MARIADB_SERVER_REF='mysql://root@127.0.0.1:3307?password_env=GITDATA_EXAMPLE_MARIADB_PASSWORD'
MARIADB_REF='mysql://root@127.0.0.1:3307/gitdata_example?password_env=GITDATA_EXAMPLE_MARIADB_PASSWORD'

gitdata ls "$MARIADB_SERVER_REF"  # databases visible to root
gitdata ls "$MARIADB_REF"         # tables in gitdata_example
gitdata ls "${MARIADB_REF}#customers"
gitdata scan --limit 2 "${MARIADB_REF}#customers"
```

Remove the disposable database when finished:

```bash
docker rm -f gitdata-example-mariadb
```

## Running the complete test suite locally

Docker is the only host dependency for the complete Python 3.9 test matrix:

```bash
bash tests/run_with_docker.sh
```

The runner builds a disposable test image, runs the general and SQLite suites,
and then starts MariaDB, PostgreSQL, and Oracle Free Lite one at a time. Each
database container and network is removed before the next service starts and is
also cleaned up if a test fails.

The service images are pinned by digest. They can be replaced without editing
the script by setting `GITDATA_TEST_MARIADB_IMAGE`,
`GITDATA_TEST_POSTGRES_IMAGE`, or `GITDATA_TEST_ORACLE_IMAGE`.

## Oracle Database

Oracle support uses the Python DB-API driver `python-oracledb`, which defaults
to Thin mode. The adapter does not initialize Thick mode, so Oracle Instant
Client is not required. The driver is optional and is loaded only when an
Oracle connection is requested:

```bash
pip install 'gitdata-lib[oracle]'
```

Connect with an Oracle service name:

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

A complete `dsn` can be supplied instead of `host`, `port`, and
`service_name`. Installing `gitdata-lib` without the `oracle` extra does not
install or import `python-oracledb`; requesting an Oracle connection in that
case reports the extra that must be installed.

The Oracle integration tests use these environment variables:

- `GITDATA_TEST_ORACLE_USER`
- `GITDATA_TEST_ORACLE_PASSWORD`
- `GITDATA_TEST_ORACLE_SERVICE_NAME`
- `GITDATA_TEST_ORACLE_HOST` (defaults to `127.0.0.1`)
- `GITDATA_TEST_ORACLE_PORT` (defaults to `1521`)

They have been exercised against Oracle Free using the
`container-registry.oracle.com/database/free:latest` container image.
