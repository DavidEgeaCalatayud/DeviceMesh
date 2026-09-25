#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
VERSION="${1:-0.2.0}"
OUT="${2:-$ROOT/dist/agents/linux}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$OUT" "$WORK/root/opt/devicemesh/lib" "$WORK/root/opt/devicemesh/bin" \
  "$WORK/root/etc/systemd/system" "$WORK/root/etc/devicemesh" "$WORK/root/var/lib/devicemesh"

python3 -m pip install --disable-pip-version-check --no-compile --target "$WORK/root/opt/devicemesh/lib" \
  "$ROOT/agents/linux/agent"

cat > "$WORK/root/opt/devicemesh/bin/devicemesh-linux-agent" <<'SH'
#!/bin/sh
export PYTHONPATH=/opt/devicemesh/lib${PYTHONPATH:+:$PYTHONPATH}
exec /usr/bin/python3 -m devicemesh_linux_agent "$@"
SH
chmod 0755 "$WORK/root/opt/devicemesh/bin/devicemesh-linux-agent"
install -m 0644 "$ROOT/agents/linux/systemd/devicemesh-agent.service" \
  "$WORK/root/etc/systemd/system/devicemesh-agent.service"
cat > "$WORK/root/etc/devicemesh/agent.env.example" <<'ENV'
DEVICEMESH_SERVER=https://mesh.example.com
DEVICEMESH_AGENT_ID=replace-me
DEVICEMESH_INTERVAL_SECONDS=30
DEVICEMESH_ENROLLMENT_TOKEN=replace-me-on-first-start
ENV

cat > "$WORK/after-install.sh" <<'SH'
#!/bin/sh
set -e
if ! getent group devicemesh >/dev/null 2>&1; then
  groupadd --system devicemesh
fi
if ! id devicemesh >/dev/null 2>&1; then
  useradd --system --gid devicemesh --home-dir /var/lib/devicemesh --shell /usr/sbin/nologin devicemesh
fi
install -d -o devicemesh -g devicemesh -m 0700 /var/lib/devicemesh
install -d -o root -g devicemesh -m 0750 /etc/devicemesh
systemctl daemon-reload >/dev/null 2>&1 || true
printf '%s\n' 'DeviceMesh agent installed. Configure /etc/devicemesh/agent.env, then run:'
printf '%s\n' '  systemctl enable --now devicemesh-agent'
SH
chmod 0755 "$WORK/after-install.sh"

cat > "$WORK/before-remove.sh" <<'SH'
#!/bin/sh
systemctl disable --now devicemesh-agent >/dev/null 2>&1 || true
SH
chmod 0755 "$WORK/before-remove.sh"

cat > "$WORK/after-remove.sh" <<'SH'
#!/bin/sh
systemctl daemon-reload >/dev/null 2>&1 || true
# Credentials and state in /var/lib/devicemesh are intentionally retained across upgrades/removal.
SH
chmod 0755 "$WORK/after-remove.sh"

for TYPE in deb rpm; do
  fpm -s dir -t "$TYPE" \
    -n devicemesh-linux-agent \
    -v "$VERSION" \
    --iteration 1 \
    --architecture "$(uname -m | sed 's/x86_64/x86_64/')" \
    --description "DeviceMesh authenticated Linux telemetry and operations agent" \
    --url "https://github.com/DavidEgeaCalatayud/DeviceMesh" \
    --license "MIT" \
    --depends python3 \
    --after-install "$WORK/after-install.sh" \
    --before-remove "$WORK/before-remove.sh" \
    --after-remove "$WORK/after-remove.sh" \
    --package "$OUT/" \
    -C "$WORK/root" .
done

sha256sum "$OUT"/*.{deb,rpm} > "$OUT/SHA256SUMS"
