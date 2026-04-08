# Changelog
All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- add initial encryption module and unit tests
- refactor secrets module into a backend-agnostic core with pluggable storage
- add `GITDATA_ENCRYPTION_KEY` and docker `/run/secrets` key resolution for secrets
- mask secret values by default in secrets listing APIs

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
