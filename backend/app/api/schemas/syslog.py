from datetime import datetime

from pydantic import BaseModel


class SyslogMessageResponse(BaseModel):
    id: int
    receivedAt: datetime
    sourceAddress: str
    deviceId: str | None
    facility: int
    severity: int
    hostname: str | None
    appName: str | None
    procId: str | None
    msgId: str | None
    message: str
    protocol: str
