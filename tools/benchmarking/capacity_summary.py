from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tables(report: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = report.get("tables", [])
    assert isinstance(rows, list)
    return {
        str(row["table_name"]): row
        for row in rows
        if isinstance(row, dict) and "table_name" in row
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize DeviceMesh capacity/soak evidence")
    parser.add_argument("directory")
    parser.add_argument("--output")
    parser.add_argument("--partition-review-rows", type=int, default=10_000_000)
    args = parser.parse_args()

    directory = Path(args.directory)
    capacity_files = sorted(directory.glob("capacity-*.json"))
    load_files = sorted(directory.glob("load-*.json"))
    if len(capacity_files) < 2:
        parser.error("at least two capacity snapshots are required")
    if not load_files:
        parser.error("at least one load report is required")

    capacity = [_read(path) for path in capacity_files]
    loads = [_read(path) for path in load_files]
    first = capacity[0]
    last = capacity[-1]
    start = datetime.fromisoformat(str(first["generatedAt"]))
    end = datetime.fromisoformat(str(last["generatedAt"]))
    duration_hours = max((end - start).total_seconds() / 3600.0, 1e-9)

    first_tables = _tables(first)
    last_tables = _tables(last)
    table_growth: list[dict[str, object]] = []
    partition_candidates: list[str] = []
    for name in sorted(set(first_tables) | set(last_tables)):
        before = first_tables.get(name, {})
        after = last_tables.get(name, {})
        before_bytes = int(before.get("total_bytes", 0) or 0)
        after_bytes = int(after.get("total_bytes", 0) or 0)
        before_rows = int(before.get("live_rows", 0) or 0)
        after_rows = int(after.get("live_rows", 0) or 0)
        dead_rows = int(after.get("dead_rows", 0) or 0)
        row_total = after_rows + dead_rows
        dead_ratio = dead_rows / row_total if row_total else 0.0
        growth = after_bytes - before_bytes
        if after_rows >= args.partition_review_rows and name in {
            "metric_samples",
            "metric_hourly_rollups",
            "device_events",
            "device_observations",
            "synthetic_check_results",
            "network_interface_counters",
            "syslog_messages",
            "audit_log",
            "security_audit_events",
            "notification_deliveries",
        }:
            partition_candidates.append(name)
        table_growth.append(
            {
                "table": name,
                "rowsBefore": before_rows,
                "rowsAfter": after_rows,
                "rowDelta": after_rows - before_rows,
                "bytesBefore": before_bytes,
                "bytesAfter": after_bytes,
                "byteDelta": growth,
                "bytesPerHour": growth / duration_hours,
                "indexBytesAfter": int(after.get("index_bytes", 0) or 0),
                "deadTupleRatioAfter": dead_ratio,
                "sequenceScansAfter": int(after.get("seq_scans", 0) or 0),
                "indexScansAfter": int(after.get("index_scans", 0) or 0),
            }
        )

    database_before = int(first.get("databaseBytes", 0) or 0)
    database_after = int(last.get("databaseBytes", 0) or 0)
    max_connection_utilization = max(
        float(
            (
                report.get("connections", {})
                if isinstance(report.get("connections"), dict)
                else {}
            ).get("utilization", 0.0)
            or 0.0
        )
        for report in capacity
    )
    min_cache_hit_ratio = min(float(report.get("bufferCacheHitRatio", 1.0) or 0.0) for report in capacity)

    failure_rates = [
        float(
            (report.get("overall", {}) if isinstance(report.get("overall"), dict) else {})
            .get("failureRate", 0.0)
            or 0.0
        )
        for report in loads
    ]
    p95_values = [
        float(
            (
                (
                    report.get("overall", {})
                    if isinstance(report.get("overall"), dict)
                    else {}
                ).get("latencyMs", {})
                if isinstance(
                    (
                        report.get("overall", {})
                        if isinstance(report.get("overall"), dict)
                        else {}
                    ).get("latencyMs", {}),
                    dict,
                )
                else {}
            ).get("p95", 0.0)
            or 0.0
        )
        for report in loads
    ]
    p99_values = [
        float(
            (
                (
                    report.get("overall", {})
                    if isinstance(report.get("overall"), dict)
                    else {}
                ).get("latencyMs", {})
                if isinstance(
                    (
                        report.get("overall", {})
                        if isinstance(report.get("overall"), dict)
                        else {}
                    ).get("latencyMs", {}),
                    dict,
                )
                else {}
            ).get("p99", 0.0)
            or 0.0
        )
        for report in loads
    ]

    warnings: list[str] = []
    if max_connection_utilization >= 0.8:
        warnings.append("PostgreSQL connection utilization reached or exceeded 80%")
    if min_cache_hit_ratio < 0.95:
        warnings.append("PostgreSQL buffer-cache hit ratio fell below 95%")
    if any(float(row["deadTupleRatioAfter"]) >= 0.2 for row in table_growth):
        warnings.append("One or more tables ended with at least 20% dead tuples")
    if partition_candidates:
        warnings.append("High-volume append tables reached the partition-review row threshold")

    result = {
        "generatedAt": datetime.now().astimezone().isoformat(),
        "evidenceWindow": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "hours": duration_hours,
            "capacitySnapshots": len(capacity),
            "loadChunks": len(loads),
        },
        "database": {
            "bytesBefore": database_before,
            "bytesAfter": database_after,
            "byteDelta": database_after - database_before,
            "bytesPerHour": (database_after - database_before) / duration_hours,
            "maxConnectionUtilization": max_connection_utilization,
            "minimumBufferCacheHitRatio": min_cache_hit_ratio,
        },
        "load": {
            "maximumFailureRate": max(failure_rates, default=0.0),
            "maximumP95Ms": max(p95_values, default=0.0),
            "maximumP99Ms": max(p99_values, default=0.0),
        },
        "partitionReview": {
            "rowThreshold": args.partition_review_rows,
            "candidates": partition_candidates,
            "note": "A threshold hit triggers review; it does not automatically require partitioning.",
        },
        "tables": table_growth,
        "warnings": warnings,
    }
    payload = json.dumps(result, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
