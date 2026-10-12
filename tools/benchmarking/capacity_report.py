from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture PostgreSQL capacity evidence for DeviceMesh")
    parser.add_argument("--database-url", default=os.getenv("DEVICEMESH_DATABASE_URL"))
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DEVICEMESH_DATABASE_URL is required")

    engine = create_engine(args.database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        database_size = int(
            connection.scalar(text("SELECT pg_database_size(current_database())")) or 0
        )
        connections = int(
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database()"
                )
            )
            or 0
        )
        max_connections = int(connection.scalar(text("SHOW max_connections")) or 0)
        cache = connection.execute(
            text(
                "SELECT "
                "sum(blks_hit)::bigint AS hits, "
                "sum(blks_read)::bigint AS reads "
                "FROM pg_stat_database WHERE datname = current_database()"
            )
        ).mappings().one()
        hits = int(cache["hits"] or 0)
        reads = int(cache["reads"] or 0)
        cache_hit_ratio = hits / (hits + reads) if hits + reads else 1.0

        tables = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT "
                    "relname AS table_name, "
                    "n_live_tup::bigint AS live_rows, "
                    "n_dead_tup::bigint AS dead_rows, "
                    "seq_scan::bigint AS seq_scans, "
                    "idx_scan::bigint AS index_scans, "
                    "pg_total_relation_size(relid)::bigint AS total_bytes, "
                    "pg_relation_size(relid)::bigint AS table_bytes, "
                    "pg_indexes_size(relid)::bigint AS index_bytes "
                    "FROM pg_stat_user_tables "
                    "ORDER BY pg_total_relation_size(relid) DESC, relname"
                )
            ).mappings()
        ]
        indexes = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT "
                    "schemaname, relname AS table_name, indexrelname AS index_name, "
                    "idx_scan::bigint AS scans, "
                    "pg_relation_size(indexrelid)::bigint AS bytes "
                    "FROM pg_stat_user_indexes "
                    "ORDER BY pg_relation_size(indexrelid) DESC, indexrelname"
                )
            ).mappings()
        ]

    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "databaseBytes": database_size,
        "connections": {
            "activeAndIdle": connections,
            "configuredMaximum": max_connections,
            "utilization": connections / max_connections if max_connections else 0.0,
        },
        "bufferCacheHitRatio": cache_hit_ratio,
        "tables": tables,
        "indexes": indexes,
    }
    payload = json.dumps(report, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
