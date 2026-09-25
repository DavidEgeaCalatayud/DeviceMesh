#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"
require_config
# Run from the reviewed target release checkout, preserving .env.production/.secrets.
compose build --pull api web
"$ROOT/tools/deployment/backup.sh"
compose stop api worker
# On migration failure, writers stay stopped. Never auto-downgrade a database.
compose run --rm migrate
compose up -d --wait --wait-timeout 180 api worker web proxy
"$ROOT/tools/deployment/smoke.sh"
