"""DeviceMesh Linux agent.

The Linux adapter follows the same authenticated heartbeat, telemetry and controlled
remote-operation contracts as the Windows reference agent. Remote operations are a
fixed allowlist; this module intentionally exposes no shell or process-execution primitive.
"""

from __future__ import annotations

import os
import platform
import socket
import stat
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

import httpx
import psutil

TELEMETRY_COLLECT: Final = "telemetry.collect"
INVENTORY_REFRESH: Final = "inventory.refresh"
AGENT_HEALTH_CHECK: Final = "agent.health_check"
ALLOWED_OPERATIONS: Final = frozenset(
    {TELEMETRY_COLLECT, INVENTORY_REFRESH, AGENT_HEALTH_CHECK}
)


@dataclass(frozen=True, slots=True)
class AgentConfig:
    server: str
    agent_id: str
    interval_seconds: int
    enrollment_token: str | None
    credential_file: Path
    credential_override: str | None = None

    @classmethod
    def from_environment(cls) -> AgentConfig:
        default_state = Path(
            os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
        ) / "devicemesh"
        interval = int(os.getenv("DEVICEMESH_INTERVAL_SECONDS", "30"))
        return cls(
            server=os.getenv("DEVICEMESH_SERVER", "http://localhost:8000").rstrip("/"),
            agent_id=os.getenv("DEVICEMESH_AGENT_ID", socket.gethostname()),
            interval_seconds=max(5, interval),
            enrollment_token=os.getenv("DEVICEMESH_ENROLLMENT_TOKEN"),
            credential_file=Path(
                os.getenv(
                    "DEVICEMESH_CREDENTIAL_FILE",
                    str(default_state / "agent.credential"),
                )
            ),
            credential_override=os.getenv("DEVICEMESH_AGENT_CREDENTIAL"),
        )


class CredentialStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> str | None:
        if not self._path.exists():
            return None
        value = self._path.read_text(encoding="utf-8").strip()
        return value or None

    def save(self, credential: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(credential.strip() + "\n", encoding="utf-8")
        self._path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.startswith("#"):
                continue
            key, raw_value = line.split("=", 1)
            values[key] = raw_value.strip().strip('"')
    except OSError:
        return {}
    return values


def _manufacturer() -> str | None:
    for path in (
        Path("/sys/class/dmi/id/sys_vendor"),
        Path("/sys/devices/virtual/dmi/id/sys_vendor"),
    ):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return None


def identity_payload() -> dict[str, object]:
    addresses = psutil.net_if_addrs()
    ip_addresses: set[str] = set()
    mac_addresses: set[str] = set()
    for interface_addresses in addresses.values():
        for address in interface_addresses:
            if address.family == socket.AF_INET:
                if not address.address.startswith("127."):
                    ip_addresses.add(address.address)
            elif address.family == socket.AF_INET6:
                normalized = address.address.split("%", 1)[0]
                if normalized != "::1":
                    ip_addresses.add(normalized)
            elif address.family == psutil.AF_LINK:
                mac = address.address.upper().replace("-", ":")
                if mac and mac != "00:00:00:00:00:00":
                    mac_addresses.add(mac)

    release = _os_release()
    return {
        "hostname": socket.gethostname(),
        "operatingSystem": release.get("NAME", "Linux"),
        "operatingSystemVersion": release.get("VERSION_ID") or platform.release(),
        "architecture": platform.machine() or None,
        "manufacturer": _manufacturer(),
        "ipAddresses": sorted(ip_addresses),
        "macAddresses": sorted(mac_addresses),
    }


def metric_payloads() -> list[dict[str, object]]:
    metrics: list[dict[str, object]] = []

    metrics.append(
        {
            "name": "host.cpu.utilization.percent",
            "value": float(psutil.cpu_percent(interval=None)),
            "unit": "percent",
        }
    )

    memory = psutil.virtual_memory()
    metrics.extend(
        [
            {
                "name": "host.memory.total.bytes",
                "value": float(memory.total),
                "unit": "bytes",
            },
            {
                "name": "host.memory.used.bytes",
                "value": float(memory.used),
                "unit": "bytes",
            },
            {
                "name": "host.memory.utilization.percent",
                "value": float(memory.percent),
                "unit": "percent",
            },
        ]
    )

    try:
        disk = psutil.disk_usage("/")
        metrics.extend(
            [
                {"name": "host.disk.total.bytes", "value": float(disk.total), "unit": "bytes"},
                {"name": "host.disk.free.bytes", "value": float(disk.free), "unit": "bytes"},
                {"name": "host.disk.used.bytes", "value": float(disk.used), "unit": "bytes"},
                {
                    "name": "host.disk.utilization.percent",
                    "value": float(disk.percent),
                    "unit": "percent",
                },
            ]
        )
    except OSError:
        pass

    network = psutil.net_io_counters()
    if network is not None:
        metrics.extend(
            [
                {
                    "name": "host.network.received.bytes",
                    "value": float(network.bytes_recv),
                    "unit": "bytes",
                },
                {
                    "name": "host.network.sent.bytes",
                    "value": float(network.bytes_sent),
                    "unit": "bytes",
                },
            ]
        )

    metrics.append(
        {
            "name": "host.uptime.seconds",
            "value": max(0.0, time.time() - float(psutil.boot_time())),
            "unit": "seconds",
        }
    )
    return metrics


def heartbeat_payload(agent_id: str, timestamp: datetime | None = None) -> dict[str, object]:
    current = timestamp or utc_now()
    return {
        "type": "heartbeat",
        "protocolVersion": 1,
        "agentId": agent_id,
        "timestamp": current.isoformat(),
        "device": identity_payload(),
    }


def telemetry_payload(agent_id: str, timestamp: datetime | None = None) -> dict[str, object]:
    current = timestamp or utc_now()
    return {
        "type": "telemetry",
        "protocolVersion": 1,
        "agentId": agent_id,
        "timestamp": current.isoformat(),
        "metrics": metric_payloads(),
    }


class DeviceMeshLinuxAgent:
    def __init__(
        self,
        config: AgentConfig,
        *,
        client: httpx.Client | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self.config = config
        self.client = client or httpx.Client(base_url=config.server, timeout=10.0)
        self.credential_store = credential_store or CredentialStore(config.credential_file)
        self._credential: str | None = None

    def close(self) -> None:
        self.client.close()

    def ensure_credential(self) -> str:
        if self._credential:
            return self._credential
        if self.config.credential_override:
            self._credential = self.config.credential_override
            return self._credential

        stored = self.credential_store.load()
        if stored:
            self._credential = stored
            return stored

        if not self.config.enrollment_token:
            raise RuntimeError(
                "No agent credential is stored and DEVICEMESH_ENROLLMENT_TOKEN is not set."
            )
        response = self.client.post(
            "/api/v1/agents/enroll",
            json={
                "token": self.config.enrollment_token,
                "agentId": self.config.agent_id,
            },
        )
        response.raise_for_status()
        payload = response.json()
        credential = payload.get("credential")
        if not isinstance(credential, str) or not credential.strip():
            raise RuntimeError("Agent enrollment did not return a credential.")
        self.credential_store.save(credential)
        self._credential = credential
        return credential

    def _auth_headers(self) -> dict[str, str]:
        credential = self.ensure_credential()
        return {
            "Authorization": f"Agent {credential}",
            "X-DeviceMesh-Agent-ID": self.config.agent_id,
            "X-DeviceMesh-Timestamp": utc_now().isoformat(),
            "X-DeviceMesh-Nonce": uuid4().hex,
        }

    def _post_authenticated(
        self,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> httpx.Response:
        response = self.client.post(path, json=payload or {}, headers=self._auth_headers())
        response.raise_for_status()
        return response

    def publish_heartbeat(self) -> None:
        self._post_authenticated(
            "/api/v1/agents/heartbeat",
            heartbeat_payload(self.config.agent_id),
        )

    def publish_telemetry(self) -> None:
        self._post_authenticated(
            "/api/v1/agents/telemetry",
            telemetry_payload(self.config.agent_id),
        )

    def claim_operation(self) -> dict[str, object] | None:
        response = self.client.post(
            "/api/v1/agents/operations/claim",
            json={},
            headers=self._auth_headers(),
        )
        if response.status_code == 204:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Remote operation claim returned an invalid payload.")
        return payload

    def complete_operation(
        self,
        operation_id: str,
        *,
        succeeded: bool,
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        self._post_authenticated(
            f"/api/v1/agents/operations/{operation_id}/complete",
            {
                "status": "succeeded" if succeeded else "failed",
                "result": result or {},
                "error": error[:1024] if error else None,
            },
        )

    def execute_operation(
        self,
        operation: dict[str, object],
    ) -> tuple[bool, dict[str, object], str | None]:
        operation_type = operation.get("operationType")
        arguments = operation.get("arguments", {})
        if not isinstance(operation_type, str) or operation_type not in ALLOWED_OPERATIONS:
            return False, {}, f"unsupported remote operation type: {operation_type}"
        if not isinstance(arguments, dict) or arguments:
            return False, {}, "operation arguments are not supported by the Linux V1.1 executor"

        if operation_type == TELEMETRY_COLLECT:
            self.publish_telemetry()
            return True, {"collectedAt": utc_now().isoformat()}, None
        if operation_type == INVENTORY_REFRESH:
            self.publish_heartbeat()
            return True, {"refreshedAt": utc_now().isoformat()}, None
        return (
            True,
            {
                "agentId": self.config.agent_id,
                "status": "ok",
                "checkedAt": utc_now().isoformat(),
                "platform": "linux",
            },
            None,
        )

    def process_one_operation(self) -> None:
        operation = self.claim_operation()
        if operation is None:
            return
        operation_id = operation.get("id")
        if not isinstance(operation_id, str) or not operation_id:
            raise RuntimeError("Remote operation claim has no valid id.")
        try:
            succeeded, result, error = self.execute_operation(operation)
        except Exception as exc:  # isolate executor failure from the agent loop
            succeeded, result, error = False, {}, str(exc)
        self.complete_operation(
            operation_id,
            succeeded=succeeded,
            result=result,
            error=error,
        )

    def run_cycle(self) -> None:
        self.publish_heartbeat()
        self.publish_telemetry()
        self.process_one_operation()

    def run_forever(self) -> None:
        while True:
            try:
                self.run_cycle()
            except httpx.HTTPError as exc:
                print(f"DeviceMesh agent request failed: {exc}", flush=True)
            except RuntimeError as exc:
                print(f"DeviceMesh agent configuration/runtime error: {exc}", flush=True)
            time.sleep(self.config.interval_seconds)


def main() -> None:
    agent = DeviceMeshLinuxAgent(AgentConfig.from_environment())
    try:
        agent.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        agent.close()


if __name__ == "__main__":
    main()
