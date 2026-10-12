from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select

from app.infrastructure.database import AgentRow, DeviceRow, SessionFactory
from app.infrastructure.repositories.mobile_push import MobilePushSubscriptionRow
from app.infrastructure.repositories.nms import NetworkManagementTargetRow
from app.infrastructure.repositories.synthetics import (
    ServiceIncidentRow,
    SyntheticMonitorRow,
    SyntheticProbeRow,
)
from app.infrastructure.repositories.syslog import SyslogMessageRow

router = APIRouter(prefix="/api/v1/system", tags=["ecosystem"])


@router.get("/ecosystem")
def ecosystem_readiness() -> dict[str, object]:
    with SessionFactory() as session:
        devices = int(session.scalar(select(func.count(DeviceRow.id))) or 0)
        online_devices = int(
            session.scalar(
                select(func.count(DeviceRow.id)).where(DeviceRow.status == "online")
            )
            or 0
        )
        agents = int(session.scalar(select(func.count(AgentRow.id))) or 0)
        monitors = int(session.scalar(select(func.count(SyntheticMonitorRow.id))) or 0)
        probes = int(session.scalar(select(func.count(SyntheticProbeRow.id))) or 0)
        nms_targets = int(
            session.scalar(select(func.count(NetworkManagementTargetRow.id))) or 0
        )
        push_subscriptions = int(
            session.scalar(
                select(func.count(MobilePushSubscriptionRow.id)).where(
                    MobilePushSubscriptionRow.enabled.is_(True)
                )
            )
            or 0
        )
        open_incidents = int(
            session.scalar(
                select(func.count(ServiceIncidentRow.id)).where(
                    ServiceIncidentRow.state == "open"
                )
            )
            or 0
        )
        syslog_messages = int(
            session.scalar(select(func.count(SyslogMessageRow.id))) or 0
        )

    components: list[dict[str, object]] = [
        {
            "id": "backend-api",
            "label": "Backend API",
            "softwareStatus": "ready",
            "acceptance": "integrated",
        },
        {
            "id": "web-console",
            "label": "Web operator console",
            "softwareStatus": "ready",
            "acceptance": "integrated",
        },
        {
            "id": "nms",
            "label": "SNMPv3 / LLDP-CDP / Syslog NMS",
            "softwareStatus": "ready",
            "acceptance": "integrated",
        },
        {
            "id": "windows-agent",
            "label": "Windows agent",
            "softwareStatus": "ready",
            "acceptance": "integrated",
        },
        {
            "id": "linux-agent",
            "label": "Linux agent",
            "softwareStatus": "ready",
            "acceptance": "integrated",
        },
        {
            "id": "macos-agent",
            "label": "macOS agent",
            "softwareStatus": "ready",
            "acceptance": "integrated",
        },
        {
            "id": "distributed-probe",
            "label": "Distributed synthetic probe",
            "softwareStatus": "ready",
            "acceptance": "integrated",
        },
        {
            "id": "android",
            "label": "Android operator client",
            "softwareStatus": "ready",
            "acceptance": "external_evidence_required",
        },
        {
            "id": "ios",
            "label": "iOS operator client",
            "softwareStatus": "ready",
            "acceptance": "external_evidence_required",
        },
        {
            "id": "esp32",
            "label": "ESP32 hardware probe",
            "softwareStatus": "ready",
            "acceptance": "external_evidence_required",
        },
    ]
    external_gates: list[dict[str, str]] = [
        {
            "id": "capacity-profiles",
            "label": "Retained 10/100/1000-agent capacity reports",
            "status": "external_evidence_required",
        },
        {
            "id": "long-soak",
            "label": "Retained 24/48-hour sustained soak",
            "status": "external_evidence_required",
        },
        {
            "id": "mobile-distribution",
            "label": "Signed physical install + FCM/APNs + Play/TestFlight evidence",
            "status": "external_evidence_required",
        },
        {
            "id": "ble-hardware",
            "label": "Android/iOS BLE provisioning against reference ESP32",
            "status": "external_evidence_required",
        },
        {
            "id": "esp32-hil",
            "label": "ESP32 HIL matrix including sensor/offline/OTA/rollback/eFuse",
            "status": "external_evidence_required",
        },
    ]
    return {
        "generatedAt": datetime.now(UTC),
        "softwareComplete": all(
            component["softwareStatus"] == "ready" for component in components
        ),
        "overallStatus": "software_ready_external_acceptance_pending",
        "components": components,
        "externalGates": external_gates,
        "runtime": {
            "devices": devices,
            "onlineDevices": online_devices,
            "agents": agents,
            "syntheticMonitors": monitors,
            "syntheticProbes": probes,
            "nmsTargets": nms_targets,
            "mobilePushSubscriptions": push_subscriptions,
            "openIncidents": open_incidents,
            "syslogMessages": syslog_messages,
        },
    }
