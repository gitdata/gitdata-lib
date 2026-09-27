# GitData Lib
Data Wrangling for Everyone.

GitData is a fast, scalable, distributed data exploration system
with a rich set of commands that provide ways to gather, manage and query data in an unusually straightforward way.

## Direct inspection

`ls` and `scan` inspect live Connector output directly. They do not initialize a
repository, digest the data into facts, or write to a store.

```bash
# List CSV columns and profile up to 100,000 rows.
gitdata ls customers.csv
gitdata scan customers.csv

# List SQLite tables, inspect one table, and profile a bounded sample.
gitdata ls example.sqlite
gitdata ls 'example.sqlite#customers'
gitdata scan --limit 1000 'example.sqlite#customers'
```

CSV rows and SQLite query results are traversed lazily. A sampled report marks
cardinality as approximate and reports the number of rows examined as a lower
bound. A complete traversal reports the exact row count.

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
