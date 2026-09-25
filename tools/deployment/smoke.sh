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
domain=$(setting DEVICEMESH_DOMAIN)
curl --fail --silent --show-error --max-time 20 "https://$domain/" >/dev/null
printf '%s\n' 'HTTPS web smoke passed.'
