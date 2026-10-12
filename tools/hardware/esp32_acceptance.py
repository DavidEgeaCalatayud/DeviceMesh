from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import serial

_AGENT_RE = re.compile(r"DeviceMesh ESP32 agent ([0-9a-f-]{36})", re.IGNORECASE)


@dataclass(frozen=True)
class BootEvidence:
    agent_id: str
    lines: tuple[str, ...]


def capture_boot(port: str, baud: int, timeout: float) -> BootEvidence:
    with serial.Serial(port, baudrate=baud, timeout=0.5) as stream:
        stream.dtr = False
        stream.rts = True
        time.sleep(0.1)
        stream.rts = False
        deadline = time.monotonic() + timeout
        lines: list[str] = []
        agent_id: str | None = None
        while time.monotonic() < deadline:
            raw = stream.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            lines.append(line)
            match = _AGENT_RE.search(line)
            if match:
                agent_id = match.group(1).lower()
            if agent_id and any(
                marker in line
                for marker in (
                    "DeviceMesh config endpoint ready",
                    "Wi-Fi already provisioned",
                    "cloud cycle succeeded",
                )
            ):
                break
        if not agent_id:
            raise RuntimeError("firmware did not emit a stable DeviceMesh agent identity")
        return BootEvidence(agent_id=agent_id, lines=tuple(lines[-200:]))


def api_json(base_url: str, path: str, token: str) -> object:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def wait_for_backend(base_url: str, token: str, agent_id: str, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            devices = api_json(base_url, "/api/v1/devices", token)
            if isinstance(devices, list):
                for row in devices:
                    if isinstance(row, dict) and row.get("id") == agent_id:
                        return row
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(2)
    raise RuntimeError("DeviceMesh backend never observed the flashed ESP32")


def require_metrics(base_url: str, token: str, agent_id: str) -> list[str]:
    rows = api_json(base_url, "/api/v1/telemetry/latest", token)
    if not isinstance(rows, list):
        raise RuntimeError("telemetry endpoint returned an unexpected payload")
    names = sorted(
        {
            str(row.get("name"))
            for row in rows
            if isinstance(row, dict) and row.get("deviceId") == agent_id
        }
    )
    required = {"network.wifi.rssi.dbm", "memory.free.bytes", "system.uptime.seconds"}
    missing = required - set(names)
    if missing:
        raise RuntimeError("missing ESP32 telemetry metrics: " + ", ".join(sorted(missing)))
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="DeviceMesh ESP32 physical acceptance smoke")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--boot-timeout", type=float, default=45)
    parser.add_argument("--backend-timeout", type=float, default=90)
    parser.add_argument("--base-url", default=os.getenv("DEVICEMESH_HIL_BASE_URL"))
    parser.add_argument("--operator-token", default=os.getenv("DEVICEMESH_HIL_OPERATOR_TOKEN"))
    parser.add_argument("--output", default="artifacts/esp32-hil.json")
    args = parser.parse_args()
    if not args.base_url or not args.base_url.startswith("https://"):
        parser.error("an HTTPS DeviceMesh HIL base URL is required")
    if not args.operator_token:
        parser.error("DEVICEMESH_HIL_OPERATOR_TOKEN is required")

    first = capture_boot(args.port, args.baud, args.boot_timeout)
    second = capture_boot(args.port, args.baud, args.boot_timeout)
    if first.agent_id != second.agent_id:
        raise RuntimeError("ESP32 identity changed across hardware reset")

    device = wait_for_backend(
        args.base_url,
        args.operator_token,
        first.agent_id,
        args.backend_timeout,
    )
    metrics = require_metrics(args.base_url, args.operator_token, first.agent_id)

    evidence = {
        "agentId": first.agent_id,
        "identityStableAcrossReset": True,
        "backendStatus": device.get("status"),
        "telemetryMetrics": metrics,
        "firstBootTail": list(first.lines),
        "secondBootTail": list(second.lines),
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2)
        handle.write("\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
