#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"
command -v docker >/dev/null
docker compose version >/dev/null
python3 "$ROOT/tools/deployment/config.py" --env-file "$ENV_FILE" --init-secrets
compose config --quiet
compose build --pull api web
compose up -d postgres redis
compose run --rm migrate
compose up -d --wait --wait-timeout 180 api worker web proxy
"$ROOT/tools/deployment/smoke.sh"
