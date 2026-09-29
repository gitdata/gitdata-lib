# Changelog
All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- add direct `gitdata ls` and `gitdata scan` support for Oracle services and tables
- show actionable CLI errors for Oracle connection, authentication, service, table, and query failures
- redact inline URL passwords from debug output and escape terminal control characters in CLI listings
- show actionable CLI errors for MariaDB/MySQL connection, authentication, and database-selection failures instead of tracebacks

## [v0.0.18] - 2026-09-28
- support and test Python 3.9 through 3.12
- replace removed `collections` aliases with `collections.abc`
- update PostgreSQL and CLI dependencies for Python 3.12
- register explicit SQLite date and timestamp adapters and converters
- run pytest-based CI and local test workflows across supported Python versions and database integrations

## [v0.0.17] - 2026-09-28
- add direct `gitdata ls` and streaming `gitdata scan` for CSV, SQLite, and MariaDB refs without digestion or storage
- allow `gitdata ls` on a MariaDB server ref to list databases visible to the user
- accept canonical `database.table` selection in MariaDB/MySQL refs while retaining `#table` compatibility
- use `database-file/table.column` SQLite refs without fragment selectors
- eagerly count database rows before sampling unless `gitdata scan --no-count` is supplied
- allow SQLite column refs to scan one column and behave as leaves under `gitdata ls`
- format `gitdata scan` as a terminal-width-aware table with aligned numeric columns and bounded values
- default omitted MariaDB usernames to the current OS user and attempt passwordless authentication when no password environment variable is specified
- add reusable CSV, SQLite, and `mysqldump` examples for manual inspection
- exit cleanly without a traceback when a command is interrupted with Ctrl+C
- announce `gitdata scan` after ref validation and connection, immediately before sampling
- add `gitdata ls -l` database/table statistics, column schema, and index details
- hide database-specific system objects from `gitdata ls` unless `-a` is supplied
- distinguish node relationships from literal values with structural predicates
- preserve repeated predicate values when reading graph nodes
- escape colliding source predicates and omit factless values without dangling relationships
- verify multiple source graphs retain independent roots in memory and SQLite repositories
- require re-ingestion of older graph facts whose unprefixed relationships cannot be distinguished from literal IDs

## [v0.0.16] - 2026-09-19
- add optional Oracle Database support with `python-oracledb` Thin mode and live CI integration tests
- add initial encryption module and unit tests
- refactor secrets module into a backend-agnostic core with pluggable storage
- add `GITDATA_ENCRYPTION_KEY` and docker `/run/secrets` key resolution for secrets
- mask secret values by default in secrets listing APIs
- persist secrets in the local `.gitdata` repository via EntityStore
- add `gitdata secret` command to list, get, set, and delete secrets
- add secrets resolve API that hard-fails listing missing names
- add `gitdata secret status`, `resolve`, and `clear` for share handoff
- keep secret values out of logs, HTTP facts, and routine CLI output
- rename CLI command to `gitdata secret` (`secrets` remains an alias)
- add `gitdata init` command to initialize repositories
- switch local repository storage to a single `.gitdata` sqlite file

## [v0.0.15] - 2025-08-03
- add secrets module stub

## [v0.0.14] - 2025-08-03
- add support for environment variable style config keys

## [v0.0.13] - 2025-08-03
- make config filename a constant
- improve CLI help and `get` output readability
- expand queue tests and database-specific test configuration

## [v0.0.12] - 2024-05-01
- add `scan` command and HTTP connector support
- add SQL module and related tests
- improve CLI behavior and test/CI setup

## [v0.0.11] - 2021-12-31
- refactor CLI and connector internals
- add fake and local connector support
- continue datastore and graph/facts foundation work

## [v0.0.3] - 2021-10-10
- add CLI entrypoint and related command wiring

## [v0.0.1] - 2021-10-09
- initial packaged release with config, database, stores, queues, and connectors
