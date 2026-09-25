#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"
require_config
compose exec -T api python - <<'PY'
import json
from pathlib import Path
from urllib.request import Request, urlopen
token = Path('/run/secrets/operator_token').read_text().strip()
for path in ['/ready', '/api/v1/system/version', '/api/v1/devices', '/api/v1/service-catalog', '/api/v1/incidents']:
    request = Request('http://localhost:8000' + path, headers={'Authorization': 'Bearer ' + token})
    with urlopen(request, timeout=10) as response:
        json.load(response)
print('API, schema and authenticated reads passed.')
PY

for endpoint in 'http://127.0.0.1:9090/-/ready' 'http://127.0.0.1:3000/api/health'; do
  ready=0
  for attempt in {1..30}; do
    if curl --fail --silent --show-error --max-time 5 "$endpoint" >/dev/null; then
      ready=1
      break
    fi
    sleep 2
  done
  if [[ "$ready" != 1 ]]; then
    printf 'Observability endpoint did not become ready: %s\n' "$endpoint" >&2
    exit 1
  fi
done

curl --fail --silent --show-error --max-time 10 \
  'http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22devicemesh-api%22%7D' \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["status"] == "success" and data["data"]["result"], data'
curl --fail --silent --show-error --max-time 10 \
  'http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22devicemesh-worker%22%7D' \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["status"] == "success" and data["data"]["result"], data'
printf '%s\n' 'Prometheus and Grafana smoke passed.'

domain=$(setting DEVICEMESH_DOMAIN)
curl --fail --silent --show-error --max-time 20 "https://$domain/" >/dev/null
printf '%s\n' 'HTTPS web smoke passed.'
