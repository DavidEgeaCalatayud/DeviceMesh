#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
ENV_FILE=${DEVICEMESH_ENV_FILE:-$ROOT/.env.production}
compose() {
  docker compose --project-directory "$ROOT" --env-file "$ENV_FILE" \
    -f "$ROOT/infra/docker/docker-compose.prod.yml" "$@"
}
setting() { python3 "$ROOT/tools/deployment/config.py" --env-file "$ENV_FILE" --get "$1"; }
require_config() { python3 "$ROOT/tools/deployment/config.py" --env-file "$ENV_FILE" >/dev/null; }
