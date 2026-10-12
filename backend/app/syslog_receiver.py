from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.repositories.syslog import SqlAlchemySyslogRepository
from app.runtime import syslog_repository

logger = logging.getLogger(__name__)

_RFC5424 = re.compile(
    r"^<(?P<pri>\d{1,3})>1 "
    r"(?P<timestamp>\S+) "
    r"(?P<hostname>\S+) "
    r"(?P<app>\S+) "
    r"(?P<proc>\S+) "
    r"(?P<msgid>\S+) "
    r"(?P<structured>-|\[[^\r\n]*?\])"
    r"(?: (?P<message>.*))?$"
)
_RFC3164 = re.compile(
    r"^<(?P<pri>\d{1,3})>"
    r"(?:(?:[A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2}) )?"
    r"(?:(?P<hostname>[^ ]+) )?"
    r"(?P<message>.*)$"
)


@dataclass(frozen=True, slots=True)
class ParsedSyslog:
    facility: int
    severity: int
    hostname: str | None
    app_name: str | None
    proc_id: str | None
    msg_id: str | None
    message: str
    protocol: str


def _clean_optional(value: str | None, *, maximum: int) -> str | None:
    if value is None or value == "-":
        return None
    return value[:maximum]


def _priority(value: str) -> tuple[int, int]:
    priority = int(value)
    if not 0 <= priority <= 191:
        raise ValueError("syslog priority must be between 0 and 191")
    return priority // 8, priority % 8


def parse_syslog(payload: bytes, *, maximum_bytes: int = 8192) -> ParsedSyslog:
    if not payload or len(payload) > maximum_bytes:
        raise ValueError("syslog datagram size is invalid")
    text = payload.decode("utf-8", errors="replace").replace("\x00", "").strip()
    if not text or "\r" in text or "\n" in text:
        raise ValueError("syslog datagram must contain one bounded message")

    match = _RFC5424.fullmatch(text)
    if match is not None:
        facility, severity = _priority(match.group("pri"))
        timestamp = match.group("timestamp")
        if timestamp != "-":
            try:
                datetime.fromisoformat(timestamp)
            except ValueError as exc:
                raise ValueError("invalid RFC5424 timestamp") from exc
        return ParsedSyslog(
            facility=facility,
            severity=severity,
            hostname=_clean_optional(match.group("hostname"), maximum=255),
            app_name=_clean_optional(match.group("app"), maximum=128),
            proc_id=_clean_optional(match.group("proc"), maximum=64),
            msg_id=_clean_optional(match.group("msgid"), maximum=64),
            message=(match.group("message") or "")[:4096],
            protocol="rfc5424",
        )

    legacy = _RFC3164.fullmatch(text)
    if legacy is None:
        raise ValueError("unsupported syslog message")
    facility, severity = _priority(legacy.group("pri"))
    return ParsedSyslog(
        facility=facility,
        severity=severity,
        hostname=_clean_optional(legacy.group("hostname"), maximum=255),
        app_name=None,
        proc_id=None,
        msg_id=None,
        message=(legacy.group("message") or "")[:4096],
        protocol="rfc3164",
    )


class SyslogDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        repository: SqlAlchemySyslogRepository,
        *,
        maximum_bytes: int,
    ) -> None:
        self._repository = repository
        self._maximum_bytes = maximum_bytes

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        source_address = addr[0]
        try:
            parsed = parse_syslog(data, maximum_bytes=self._maximum_bytes)
        except ValueError:
            logger.warning(
                "rejected invalid syslog datagram",
                extra={"route": "syslog", "status": "rejected"},
            )
            return
        asyncio.create_task(self._persist(parsed, source_address))

    async def _persist(self, parsed: ParsedSyslog, source_address: str) -> None:
        try:
            await asyncio.to_thread(
                self._repository.append,
                received_at=datetime.now(UTC),
                source_address=source_address,
                facility=parsed.facility,
                severity=parsed.severity,
                hostname=parsed.hostname,
                app_name=parsed.app_name,
                proc_id=parsed.proc_id,
                msg_id=parsed.msg_id,
                message=parsed.message,
                protocol=parsed.protocol,
            )
        except Exception:
            logger.exception(
                "syslog persistence failed",
                extra={"route": "syslog", "status": "failure"},
            )


async def main() -> None:
    configure_logging(service_name="syslog-receiver")
    settings = get_settings()
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: SyslogDatagramProtocol(
            syslog_repository,
            maximum_bytes=settings.syslog_max_datagram_bytes,
        ),
        local_addr=(settings.syslog_host, settings.syslog_port),
    )
    logger.info(
        "syslog receiver started",
        extra={"route": f"{settings.syslog_host}:{settings.syslog_port}/udp"},
    )
    try:
        await asyncio.Future()
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
