#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"
require_config
umask 077
directory=${DEVICEMESH_BACKUP_DIR:-$ROOT/backups}
mkdir -p -- "$directory"
directory=$(cd -- "$directory" && pwd)
name="devicemesh-$(date -u +%Y%m%dT%H%M%SZ)-$$"
temporary=$(mktemp -d "$directory/.backup.XXXXXXXX")
trap 'rm -rf -- "$temporary"' EXIT
compose exec -T postgres pg_dump -U devicemesh_owner -d devicemesh -Fc > "$temporary/database.dump"
compose exec -T postgres pg_restore --list < "$temporary/database.dump" >/dev/null
cp -- "$ENV_FILE" "$temporary/deployment.env"
compose images --format json > "$temporary/images.json"
python3 - "$temporary" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
p = Path(sys.argv[1])
manifest = {'format': 1, 'createdAt': datetime.now(timezone.utc).isoformat(),
            'databaseSha256': hashlib.file_digest((p/'database.dump').open('rb'), 'sha256').hexdigest(),
            'secretsIncluded': False}
(p/'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY
tar -C "$temporary" -czf "$directory/$name.tar.gz.partial" database.dump deployment.env images.json manifest.json
mv -- "$directory/$name.tar.gz.partial" "$directory/$name.tar.gz"
# Retention touches only complete bundles owned by this script, after a successful backup.
retention=$(setting BACKUP_RETENTION_DAYS)
find "$directory" -maxdepth 1 -type f -name 'devicemesh-*.tar.gz' -mtime "+${retention:-30}" -delete
printf '%s\n' "$directory/$name.tar.gz"
