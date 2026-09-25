#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$(cat /run/secrets/application_password)" <<'SQL'
CREATE ROLE devicemesh_app LOGIN PASSWORD :'app_password';
GRANT CONNECT ON DATABASE devicemesh TO devicemesh_app;
GRANT USAGE ON SCHEMA public TO devicemesh_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO devicemesh_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO devicemesh_app;
SQL
