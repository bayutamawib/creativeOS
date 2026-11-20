#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv app_password APP_DB_PASSWORD
CREATE ROLE creative_app LOGIN PASSWORD :'app_password';
CREATE DATABASE creativeos OWNER creative_app;
SQL
