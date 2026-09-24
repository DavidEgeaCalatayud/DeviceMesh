import time

from devicemesh_probe.client import fetch_synthetic_monitors, publish_synthetic_results
from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.synthetics import SyntheticExecutionResult, execute_monitor


def run_synthetic_once(config: ProbeConfig) -> list[SyntheticExecutionResult]:
    token = config.require_probe_token()
    monitors = fetch_synthetic_monitors(config.server_url, token)
    results = [execute_monitor(monitor) for monitor in monitors]
    publish_synthetic_results(config.server_url, token, config.probe_id, results)
    return results


def run_synthetic_forever(config: ProbeConfig) -> None:
    token = config.require_probe_token()
    next_due: dict[str, float] = {}
    while True:
        try:
            monitors = fetch_synthetic_monitors(config.server_url, token)
            now = time.monotonic()
            active_ids = {monitor.id for monitor in monitors}
            next_due = {
                monitor_id: due
                for monitor_id, due in next_due.items()
                if monitor_id in active_ids
            }
            due_monitors = [
                monitor
                for monitor in monitors
                if next_due.get(monitor.id, 0.0) <= now
            ]
            results = [execute_monitor(monitor) for monitor in due_monitors]
            if results:
                publish_synthetic_results(config.server_url, token, config.probe_id, results)
                for monitor in due_monitors:
                    next_due[monitor.id] = now + monitor.interval_seconds
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"DeviceMesh synthetic probe cycle failed: {exc}", flush=True)

        if next_due:
            next_run = max(0.5, min(next_due.values()) - time.monotonic())
            time.sleep(min(5.0, next_run))
        else:
            time.sleep(5.0)
