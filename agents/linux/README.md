# DeviceMesh Linux Agent

The Linux agent is a Python 3.12 agent that implements the same DeviceMesh V1 protocol used by the Windows and macOS agents:

- enrollment and persistent agent credentials
- authenticated heartbeat with host/network identity
- host telemetry
- controlled pull-based remote operations

It does **not** provide arbitrary shell execution.

## Metrics

The agent currently publishes:

- `host.cpu.utilization.percent`
- `host.memory.total.bytes`
- `host.memory.used.bytes`
- `host.memory.utilization.percent`
- `host.disk.total.bytes`
- `host.disk.free.bytes`
- `host.disk.used.bytes`
- `host.disk.utilization.percent`
- `host.network.received.bytes`
- `host.network.sent.bytes`
- `host.uptime.seconds`

The metric names intentionally match the Windows agent so dashboards and alert rules remain portable across operating systems.

## Development

```bash
cd agents/linux/agent
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
ruff check . ../tests
mypy devicemesh_linux_agent.py
pytest -q
```

## Configuration

Environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DEVICEMESH_SERVER` | DeviceMesh API base URL | `http://localhost:8000` |
| `DEVICEMESH_AGENT_ID` | Stable agent identifier | hostname |
| `DEVICEMESH_INTERVAL_SECONDS` | heartbeat/telemetry loop interval | `30` |
| `DEVICEMESH_ENROLLMENT_TOKEN` | one-time initial enrollment token | none |
| `DEVICEMESH_CREDENTIAL_FILE` | persistent agent credential path | XDG state path |
| `DEVICEMESH_AGENT_CREDENTIAL` | explicit runtime credential override | none |

For a service installation, prefer a credential file rather than a credential environment override. The agent writes the credential file with mode `0600`.

After first enrollment succeeds, remove `DEVICEMESH_ENROLLMENT_TOKEN` from the persistent environment file; the stored agent credential is used for subsequent requests.

## Remote operations

The Linux V1.1 executor accepts only:

- `telemetry.collect`
- `inventory.refresh`
- `agent.health_check`

The executor rejects operation arguments. There is no shell, subprocess or executable-path operation.

## Native packages

Release CI builds `.deb` and `.rpm` artifacts plus `SHA256SUMS`. Packages vendor the Python dependencies and install this layout:

```text
/opt/devicemesh/lib/                         vendored Python package/dependencies
/opt/devicemesh/bin/devicemesh-linux-agent stable launcher
/etc/devicemesh/agent.env.example           configuration template
/etc/devicemesh/agent.env                   operator-managed configuration
/var/lib/devicemesh/                        persistent credential/state
/etc/systemd/system/devicemesh-agent.service hardened systemd unit
```

Install on Debian/Ubuntu:

```bash
sudo apt install ./devicemesh-linux-agent_<version>_amd64.deb
sudo cp /etc/devicemesh/agent.env.example /etc/devicemesh/agent.env
sudo editor /etc/devicemesh/agent.env
sudo systemctl enable --now devicemesh-agent
```

Install on RPM-family systems:

```bash
sudo rpm -U ./devicemesh-linux-agent-<version>-1.x86_64.rpm
sudo cp /etc/devicemesh/agent.env.example /etc/devicemesh/agent.env
sudo editor /etc/devicemesh/agent.env
sudo systemctl enable --now devicemesh-agent
```

The package deliberately does not auto-start an unconfigured agent. After successful enrollment, remove the one-time token from `/etc/devicemesh/agent.env` and restart the service.

## Manual systemd installation

The reference unit expects `/opt/devicemesh/bin/devicemesh-linux-agent`. For local/manual development installations you can provide that launcher yourself or use the native package. The service runs as the dedicated `devicemesh` user and uses systemd hardening (`ProtectSystem`, `NoNewPrivileges`, capability removal and a dedicated writable state directory).
