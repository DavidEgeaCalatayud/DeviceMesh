#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

cp .env.production.example .env.production
sed -i 's/mesh.example.com/mesh.failure.invalid/g' .env.production
python tools/deployment/config.py --init-secrets

cat > infra/docker/failure.override.yml <<'YAML'
services:
  api:
    ports: ["127.0.0.1:18000:8000"]
  worker:
    ports: ["127.0.0.1:19100:9100"]
YAML

compose() {
  docker compose --project-directory . --env-file .env.production \
    -f infra/docker/docker-compose.prod.yml \
    -f infra/docker/failure.override.yml "$@"
}

wait_http_code() {
  local url="$1" expected="$2" label="$3"
  for attempt in {1..40}; do
    local code
    code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 4 "$url" 2>/dev/null || true)"
    if [[ "$code" == "$expected" ]]; then
      printf '%s: observed HTTP %s\n' "$label" "$expected"
      return 0
    fi
    sleep 2
  done
  echo "$label: expected HTTP $expected from $url" >&2
  compose ps >&2 || true
  return 1
}

wait_worker_leader() {
  for attempt in {1..40}; do
    if curl --fail --silent --max-time 3 http://127.0.0.1:19100/metrics \
      | grep -Eq '^devicemesh_worker_leader 1(\.0)?$'; then
      echo "worker: scheduler leadership active"
      return 0
    fi
    sleep 2
  done
  echo "worker: scheduler leadership did not recover" >&2
  compose logs --tail 100 worker >&2 || true
  return 1
}

operator_get() {
  local path="$1"
  curl --fail --silent \
    -H "Authorization: Bearer $(cat .secrets/operator_token)" \
    "http://127.0.0.1:18000$path"
}

wait_realtime_recovery() {
  # Redis subscriptions reconnect with bounded exponential backoff (up to 30 s).
  # Keep the API process alive and retry the end-to-end acceptance flow across
  # that real recovery window instead of masking recovery with an API restart.
  for attempt in {1..4}; do
    if python tools/deployment/acceptance.py --token-file .secrets/operator_token; then
      echo "realtime: Redis subscriber recovered"
      return 0
    fi
    if [[ "$attempt" == 4 ]]; then
      echo "realtime: subscriber did not recover within the bounded retry window" >&2
      return 1
    fi
    sleep 10
  done
}

echo "[baseline] starting production services"
compose up -d --build --wait --wait-timeout 180 api worker
wait_http_code http://127.0.0.1:18000/ready 200 "baseline readiness"
wait_worker_leader

curl --fail --silent \
  -H "Authorization: Bearer $(cat .secrets/operator_token)" \
  -H 'Content-Type: application/json' \
  -d '{"name":"failure-canary","description":"durability marker for failure acceptance"}' \
  http://127.0.0.1:18000/api/v1/service-catalog >/tmp/failure-canary.json

echo "[postgres] stopping durable store"
compose stop postgres
wait_http_code http://127.0.0.1:18000/ready 503 "database outage readiness"

echo "[postgres] restoring durable store"
compose start postgres
wait_http_code http://127.0.0.1:18000/ready 200 "database recovery readiness"
wait_worker_leader
operator_get /api/v1/service-catalog \
  | python -c 'import json,sys; data=json.load(sys.stdin); assert any(x["name"] == "failure-canary" for x in data)'

echo "[redis] stopping realtime backend"
compose stop redis
wait_http_code http://127.0.0.1:18000/ready 200 "redis outage durable readiness"
operator_get /api/v1/service-catalog >/dev/null

echo "[redis] restoring realtime backend"
compose start redis
for attempt in {1..30}; do
  if compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then break; fi
  if [[ "$attempt" == 30 ]]; then echo "Redis did not recover" >&2; exit 1; fi
  sleep 2
done
wait_realtime_recovery

echo "[api] forcing process outage"
compose stop api
if curl --fail --silent --max-time 3 http://127.0.0.1:18000/health >/dev/null 2>&1; then
  echo "API remained reachable after container stop" >&2
  exit 1
fi
compose start api
wait_http_code http://127.0.0.1:18000/ready 200 "api restart readiness"
operator_get /api/v1/service-catalog \
  | python -c 'import json,sys; data=json.load(sys.stdin); assert any(x["name"] == "failure-canary" for x in data)'

echo "[worker] forcing scheduler outage"
compose stop worker
if curl --fail --silent --max-time 3 http://127.0.0.1:19100/metrics >/dev/null 2>&1; then
  echo "Worker metrics remained reachable after container stop" >&2
  exit 1
fi
compose start worker
wait_worker_leader

echo '{"status":"passed","scenarios":["postgres-outage-recovery","redis-outage-recovery","api-restart-durability","worker-restart-leadership"]}'
