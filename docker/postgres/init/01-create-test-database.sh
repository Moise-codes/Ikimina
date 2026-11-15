#!/bin/sh
# Runs once, the first time the PostgreSQL data volume is created.
#
# The official postgres image already creates POSTGRES_DB. This script adds a
# second database used only by the automated test suite, owned by the same
# application role, so tests never touch development data.
set -e

test_db="${POSTGRES_TEST_DB:-ikimina_test}"

echo "init: creating test database '${test_db}' owned by '${POSTGRES_USER}'"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "$test_db" OWNER "$POSTGRES_USER";
EOSQL
