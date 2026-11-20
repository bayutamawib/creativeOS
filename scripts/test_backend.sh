#!/bin/sh
# Create an isolated database per run, including parallel local or CI runs.
set -eu
test_db="creativeos_test_$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
docker compose exec -T postgres createdb -U postgres -O creative_app "$test_db"
cleanup() {
  docker compose exec -T postgres dropdb -U postgres --if-exists "$test_db"
}
trap cleanup EXIT
docker compose run --rm -T --no-deps --user root -e "DB_NAME=$test_db" \
  -v "$PWD/backend/tests:/app/tests:ro" backend-test sh -ec '
    pip install --disable-pip-version-check -q -r requirements-dev.txt
    ruff check app alembic tests
    mypy
    alembic upgrade head
    alembic check
    pytest -q
  '
