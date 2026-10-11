from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.schemas.syslog import SyslogMessageResponse
from app.infrastructure.repositories.syslog import SqlAlchemySyslogRepository
from app.runtime import get_syslog_repository

router = APIRouter(prefix="/api/v1/syslog", tags=["syslog"])
Repository = Annotated[SqlAlchemySyslogRepository, Depends(get_syslog_repository)]


@router.get("", response_model=list[SyslogMessageResponse])
def search_syslog(
    repository: Repository,
    device_id: Annotated[str | None, Query(alias="deviceId", max_length=128)] = None,
    source_address: Annotated[str | None, Query(alias="sourceAddress", max_length=64)] = None,
    severity: Annotated[int | None, Query(ge=0, le=7)] = None,
    facility: Annotated[int | None, Query(ge=0, le=23)] = None,
    start: datetime | None = None,
    end: datetime | None = None,
    q: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[SyslogMessageResponse]:
    rows = repository.search(
        device_id=device_id,
        source_address=source_address,
        severity=severity,
        facility=facility,
        start=start,
        end=end,
        query_text=q,
        limit=limit,
    )
    return [
        SyslogMessageResponse(
            id=row.id,
            receivedAt=row.received_at,
            sourceAddress=row.source_address,
            deviceId=row.device_id,
            facility=row.facility,
            severity=row.severity,
            hostname=row.hostname,
            appName=row.app_name,
            procId=row.proc_id,
            msgId=row.msg_id,
            message=row.message,
            protocol=row.protocol,
        )
        for row in rows
    ]
