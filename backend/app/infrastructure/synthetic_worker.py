from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.infrastructure.repositories.synthetics import SqlAlchemySyntheticRepository
from app.infrastructure.synthetics import SyntheticProbeExecutor


class SyntheticProbeWorker:
    def __init__(
        self,
        repository: SqlAlchemySyntheticRepository,
        executor: SyntheticProbeExecutor,
        *,
        probe_id: str,
        batch_size: int,
    ) -> None:
        self._repository = repository
        self._executor = executor
        self._probe_id = probe_id
        self._batch_size = batch_size

    async def run_due(self, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        monitors = await asyncio.to_thread(
            self._repository.claim_due,
            now=current,
            limit=self._batch_size,
        )
        for monitor in monitors:
            outcome = await self._executor.execute(monitor)
            await asyncio.to_thread(
                self._repository.record_result,
                monitor_id=monitor.id,
                success=outcome.success,
                latency_ms=outcome.latency_ms,
                http_status=outcome.http_status,
                error_kind=outcome.error_kind,
                error=outcome.error,
                probe_id=self._probe_id,
                probe_location="backend-local",
                checked_at=datetime.now(UTC),
            )
        return len(monitors)
