# DeviceMesh Linux Agent

The Linux agent is a Python 3.12 agent that implements the same DeviceMesh V1 protocol used by the Windows agent:

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

The V1.1 executor rejects operation arguments. There is no shell, subprocess or executable-path operation.

## systemd

A hardened reference unit is available at `systemd/devicemesh-agent.service`.

One possible installation layout is:

```text
/opt/devicemesh/venv/        Python virtual environment
/etc/devicemesh/agent.env    non-secret configuration + temporary enrollment token
/var/lib/devicemesh/         persistent agent credential
```

Example `/etc/devicemesh/agent.env`:

```bash
DEVICEMESH_SERVER=https://devicemesh.example.internal
DEVICEMESH_AGENT_ID=warehouse-linux-01
DEVICEMESH_INTERVAL_SECONDS=30
DEVICEMESH_ENROLLMENT_TOKEN=<one-time-token>
```

Install the package into the service virtual environment and then enable the unit:

```bash
python3.12 -m venv /opt/devicemesh/venv
/opt/devicemesh/venv/bin/pip install /path/to/DeviceMesh/agents/linux/agent
sudo cp systemd/devicemesh-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now devicemesh-agent
```

After successful enrollment, remove the one-time token from `/etc/devicemesh/agent.env` and restart the service.
