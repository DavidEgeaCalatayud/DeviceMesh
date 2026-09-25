#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"
require_config
if [[ $# != 2 || $2 != --replace-database ]]; then
  printf '%s\n' 'Usage: restore.sh BACKUP.tar.gz --replace-database (stops writers and replaces all database contents)' >&2
  exit 2
fi
backup=$(realpath -- "$1")
umask 077
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
# Read only the expected regular members; never extract archive paths or symlinks.
python3 - "$backup" "$temporary" <<'PY'
import hashlib, json, sys, tarfile
from pathlib import Path
target = Path(sys.argv[2])
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    for name in ('database.dump', 'manifest.json'):
        member = archive.getmember(name)
        if not member.isfile():
            raise SystemExit('Invalid backup member')
        source = archive.extractfile(member)
        if source is None:
            raise SystemExit('Missing backup member')
        with (target/name).open('wb') as stream:
            import shutil
            shutil.copyfileobj(source, stream)
manifest = json.loads((target/'manifest.json').read_text())
with (target/'database.dump').open('rb') as stream:
    checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
if manifest.get('format') != 1 or manifest.get('databaseSha256') != checksum:
    raise SystemExit('Backup checksum or format mismatch')
PY
compose exec -T postgres pg_restore --list < "$temporary/database.dump" >/dev/null
# Keep a recovery point before the destructive step. Failure stops here.
"$ROOT/tools/deployment/backup.sh"
# Restore into a new database before stopping writers or touching the live name.
replacement="devicemesh_restore_$(date +%s)_$$"
previous="devicemesh_before_restore_$(date +%s)_$$"
compose exec -T postgres createdb -U devicemesh_owner "$replacement"
compose exec -T postgres pg_restore -U devicemesh_owner -d "$replacement" \
  --no-owner --exit-on-error --single-transaction < "$temporary/database.dump"
compose stop api worker
compose exec -T postgres psql -U devicemesh_owner -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='devicemesh' AND pid <> pg_backend_pid()" >/dev/null
compose exec -T postgres psql -U devicemesh_owner -d postgres -v ON_ERROR_STOP=1 \
  -c "ALTER DATABASE devicemesh RENAME TO $previous"
compose exec -T postgres psql -U devicemesh_owner -d postgres -v ON_ERROR_STOP=1 \
  -c "ALTER DATABASE $replacement RENAME TO devicemesh"
compose run --rm migrate
compose up -d --wait --wait-timeout 180 api worker
"$ROOT/tools/deployment/smoke.sh"
printf '%s\n' "Previous database retained as $previous until you verify the restored deployment."
