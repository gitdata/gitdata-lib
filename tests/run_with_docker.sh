#!/usr/bin/env bash
# Run the complete test matrix with database services started sequentially.

set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DOCKER=${DOCKER:-docker}
RUN_ID=${GITDATA_TEST_RUN_ID-$$}
PREFIX="gitdata-test-${RUN_ID}"
MARIADB_IMAGE=${GITDATA_TEST_MARIADB_IMAGE:-mariadb:10.7@sha256:9a48ac9f196f3d4fd6fea2cab59a49df9e7ca459bf14b2f7b85a0e38a5454571}
POSTGRES_IMAGE=${GITDATA_TEST_POSTGRES_IMAGE:-postgres:18.6@sha256:86c951e05bf56c93d95d397747fb8820ac76cc3bedb78f43abd83eedbe3666ae}
ORACLE_IMAGE=${GITDATA_TEST_ORACLE_IMAGE:-container-registry.oracle.com/database/free@sha256:770ca58ab319d8cfde610b0db25c06899ce0af9591c4addfa10d2cb8f0318e65}

active_container=''
active_network=''
owned_test_image=''
remove_test_image=false

case "$RUN_ID" in
    ''|*[!A-Za-z0-9_.-]*)
        printf 'Invalid GITDATA_TEST_RUN_ID: %s\n' "$RUN_ID" >&2
        exit 2
        ;;
esac

if [[ -n "${GITDATA_TEST_IMAGE:-}" ]]; then
    TEST_IMAGE=$GITDATA_TEST_IMAGE
else
    TEST_IMAGE="gitdata-lib-tests:${RUN_ID}"
    remove_test_image=true
fi

cleanup_active() {
    local failed=0

    if [[ -n "$active_container" ]]; then
        if "$DOCKER" rm -f "$active_container" >/dev/null; then
            active_container=''
        else
            printf 'Failed to remove container %s\n' "$active_container" >&2
            failed=1
        fi
    fi
    if [[ -n "$active_network" ]]; then
        if "$DOCKER" network rm "$active_network" >/dev/null; then
            active_network=''
        else
            printf 'Failed to remove network %s\n' "$active_network" >&2
            failed=1
        fi
    fi

    return "$failed"
}

cleanup_test_image() {
    if [[ -z "$owned_test_image" ]]; then
        return
    fi

    if "$DOCKER" image rm "$owned_test_image" >/dev/null; then
        owned_test_image=''
        return
    fi

    printf 'Failed to remove test image %s\n' "$owned_test_image" >&2
    return 1
}

on_exit() {
    local status=$?
    local cleanup_failed=0
    trap - EXIT
    cleanup_active || cleanup_failed=1
    cleanup_test_image || cleanup_failed=1
    if [[ "$status" -eq 0 && "$cleanup_failed" -ne 0 ]]; then
        status=1
    fi
    exit "$status"
}
trap on_exit EXIT
trap 'exit 130' INT TERM

phase() {
    printf '\n==> %s\n' "$1"
}

start_service() {
    local service=$1
    local image=$2
    local container="${PREFIX}-${service}"
    local network="${PREFIX}-${service}"
    shift 2

    if ! active_network=$("$DOCKER" network create "$network"); then
        active_network=''
        return 1
    fi
    if ! active_container=$("$DOCKER" create \
        --name "$container" \
        --network "$active_network" \
        --network-alias "$service" \
        "$@" \
        "$image"
    ); then
        active_container=''
        return 1
    fi
    "$DOCKER" start "$active_container" >/dev/null
}

wait_for_mariadb() {
    for _ in $(seq 1 60); do
        if "$DOCKER" exec "$active_container" \
                mariadb-admin ping -h 127.0.0.1 -uroot -proot --silent \
                >/dev/null 2>&1; then
            return
        fi
        sleep 2
    done
    "$DOCKER" logs "$active_container"
    return 1
}

wait_for_postgres() {
    for _ in $(seq 1 60); do
        if "$DOCKER" exec "$active_container" \
                pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then
            return
        fi
        sleep 2
    done
    "$DOCKER" logs "$active_container"
    return 1
}

wait_for_oracle() {
    local status

    for _ in $(seq 1 60); do
        status=$("$DOCKER" inspect --format \
            '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
            "$active_container")
        if [[ "$status" == healthy ]]; then
            return
        fi
        if [[ "$status" == exited || "$status" == dead ]]; then
            "$DOCKER" logs "$active_container"
            return 1
        fi
        sleep 5
    done
    "$DOCKER" logs "$active_container"
    return 1
}

phase 'Building the Python 3.9 test image'
"$DOCKER" build -f "$ROOT/tests/Dockerfile" -t "$TEST_IMAGE" "$ROOT"
if [[ "$remove_test_image" == true ]]; then
    owned_test_image=$TEST_IMAGE
fi

phase 'Running general, Oracle unit, and SQLite tests'
"$DOCKER" run --rm "$TEST_IMAGE" sh -c '
    python -m nose -c .noserc gitdata $(printf "%s\n" tests/unittests/test_*.py | grep -v database) &&
    python -m nose -c .noserc tests/unittests/test_database_oracle.py &&
    python -m nose -c .noserc tests/unittests/test_database.py:TestSqlite3Database
'

phase 'Running MariaDB tests'
start_service mariadb "$MARIADB_IMAGE" \
    -e MARIADB_DATABASE=gitdatatest \
    -e MARIADB_ROOT_PASSWORD=root
wait_for_mariadb
"$DOCKER" run --rm \
    --network "$active_network" \
    -e GITDATA_TEST_MYSQL_DATABASE_HOST=mariadb \
    -e GITDATA_TEST_MYSQL_DATABASE_USER=root \
    -e GITDATA_TEST_MYSQL_DATABASE_PASSWORD=root \
    "$TEST_IMAGE" \
    python -m nose -c .noserc \
    tests/unittests/test_database.py:TestMySQLDatabase
cleanup_active

phase 'Running PostgreSQL tests'
start_service postgres "$POSTGRES_IMAGE" \
    -e POSTGRES_PASSWORD=password
wait_for_postgres
"$DOCKER" run --rm \
    --network "$active_network" \
    -e GITDATA_TEST_POSTGRES_DATABASE_HOST=postgres \
    -e GITDATA_TEST_POSTGRES_DATABASE_USER=postgres \
    -e GITDATA_TEST_POSTGRES_DATABASE_PASSWORD=password \
    "$TEST_IMAGE" \
    python -m nose -c .noserc \
    tests/unittests/test_database.py:TestPostgreSQLDatabase
cleanup_active

phase 'Running Oracle integration tests'
start_service oracle "$ORACLE_IMAGE" \
    -e ORACLE_PWD=GitDataCi123
wait_for_oracle
"$DOCKER" run --rm \
    --network "$active_network" \
    -e ORACLE_PWD=GitDataCi123 \
    -e GITDATA_TEST_ORACLE_HOST=oracle \
    -e GITDATA_TEST_ORACLE_PORT=1521 \
    -e GITDATA_TEST_ORACLE_SERVICE_NAME=FREEPDB1 \
    -e GITDATA_TEST_ORACLE_USER=GITDATA_TEST \
    -e GITDATA_TEST_ORACLE_PASSWORD=GitDataApp123 \
    "$TEST_IMAGE" \
    python tests/integration/setup_oracle.py
"$DOCKER" run --rm \
    --network "$active_network" \
    -e GITDATA_TEST_ORACLE_HOST=oracle \
    -e GITDATA_TEST_ORACLE_PORT=1521 \
    -e GITDATA_TEST_ORACLE_SERVICE_NAME=FREEPDB1 \
    -e GITDATA_TEST_ORACLE_USER=GITDATA_TEST \
    -e GITDATA_TEST_ORACLE_PASSWORD=GitDataApp123 \
    "$TEST_IMAGE" \
    python -m nose -c .noserc tests/integration/test_database_oracle.py
cleanup_active
cleanup_test_image

phase 'All test stages passed'
