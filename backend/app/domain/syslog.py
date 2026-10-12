from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SyslogMessage:
    id: int
    received_at: datetime
    source_address: str
    device_id: str | None
    facility: int
    severity: int
    hostname: str | None
    app_name: str | None
    proc_id: str | None
    msg_id: str | None
    message: str
    protocol: str
