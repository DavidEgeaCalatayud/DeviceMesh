#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"
require_config
backup=$("$ROOT/tools/deployment/backup.sh")
temporary=$(mktemp -d)
database="restore_check_$(date +%s)_$$"
cleanup() {
  compose exec -T postgres dropdb -U devicemesh_owner --if-exists "$database" >/dev/null
  rm -rf -- "$temporary"
}
trap cleanup EXIT
tar -xOzf "$backup" database.dump > "$temporary/database.dump"
compose exec -T postgres createdb -U devicemesh_owner "$database"
compose exec -T postgres pg_restore -U devicemesh_owner -d "$database" \
  --no-owner --exit-on-error --single-transaction < "$temporary/database.dump"
revision=$(compose exec -T postgres psql -U devicemesh_owner -d "$database" -Atc 'SELECT version_num FROM alembic_version')
expected=$(compose exec -T postgres psql -U devicemesh_owner -d devicemesh -Atc 'SELECT version_num FROM alembic_version')
[[ "$revision" == "$expected" ]]
printf '%s\n' "Restore rehearsal passed in isolated database $database."
