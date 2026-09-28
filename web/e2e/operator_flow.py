"""Browser-level smoke test for the operator application.

The browser runs the real Vite application. HTTP APIs are intercepted with stable
fixtures so the test focuses on UI/session/navigation behaviour and remains fast
and deterministic in Web CI.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from playwright.sync_api import Route, expect, sync_playwright

BASE_URL = "http://127.0.0.1:5173"

DEVICE = {
    "id": "device-1",
    "hostname": "edge-gateway-01",
    "ipAddresses": ["10.20.30.1"],
    "macAddresses": ["00:11:22:33:44:55"],
    "operatingSystem": "Linux",
    "operatingSystemVersion": "6.8",
    "architecture": "x86_64",
    "manufacturer": "DeviceMesh Lab",
    "status": "online",
    "firstSeen": "2026-09-25T10:00:00Z",
    "lastSeen": "2026-09-25T13:00:00Z",
}
SERVICE = {
    "id": "svc-1",
    "name": "Payments API",
    "description": "Primary payment processing service",
    "owner": "platform-team",
    "environment": "production",
    "criticality": "critical",
    "monitorIds": [],
    "groupIds": [],
    "dependencies": [],
    "dependents": [],
}
INCIDENT = {
    "id": "inc-1",
    "monitorId": "mon-1",
    "serviceIds": ["svc-1"],
    "deviceId": "device-1",
    "title": "Database outage",
    "severity": "SEV1",
    "status": "investigating",
    "classification": "availability",
    "openedAt": "2026-09-25T12:30:00Z",
    "resolvedAt": None,
    "assignedTo": "on-call",
    "acknowledgedAt": "2026-09-25T12:31:00Z",
    "acknowledgedBy": "operator",
    "rootCause": "",
    "resolution": "",
    "impactSummary": "Checkout is unavailable",
    "postmortem": "",
    "tags": ["payments"],
    "timeline": [],
    "correlatedIncidents": [],
}


def respond(route: Route, payload: object, status: int = 200) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))


def api_handler(route: Route) -> None:
    request = route.request
    parsed = urlparse(request.url)
    path = parsed.path
    method = request.method

    if path == "/api/v1/auth/login" and method == "POST":
        assert request.post_data_json == {"username": "operator", "password": "correct-horse"}
        respond(route, {"accessToken": "access-token", "refreshToken": "refresh-token"})
        return
    if path == "/api/v1/auth/logout" and method == "POST":
        respond(route, {"status": "signed_out"})
        return
    if path == "/api/v1/auth/me":
        respond(route, {"id": "user-1", "username": "operator", "role": "administrator", "enabled": True})
        return
    if path == "/api/v1/devices":
        respond(route, [DEVICE])
        return
    if path == "/api/v1/events":
        respond(route, [])
        return
    if path == "/api/v1/telemetry/latest":
        respond(route, [])
        return
    if path == "/api/v1/alerts":
        respond(route, [])
        return
    if path == "/api/v1/services":
        respond(route, [])
        return
    if path == "/api/v1/network/topology":
        respond(route, {"nodes": [], "edges": [], "method": "observation-segment", "approximate": True})
        return
    if path == "/api/v1/service-catalog":
        respond(route, [SERVICE])
        return
    if path == "/api/v1/service-catalog/svc-1/slos":
        respond(route, [])
        return
    if path == "/api/v1/synthetic-monitors":
        respond(route, [])
        return
    if path == "/api/v1/maintenance-windows":
        respond(route, [])
        return
    if path == "/api/v1/service-groups":
        respond(route, [])
        return
    if path == "/api/v1/incidents":
        respond(route, [INCIDENT])
        return
    if path == "/api/v1/incidents/inc-1":
        respond(route, INCIDENT)
        return

    respond(route, {"detail": f"unhandled E2E route: {method} {path}"}, status=501)


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.route("**/api/v1/**", api_handler)

        page.goto(f"{BASE_URL}/#/login")
        expect(page.get_by_role("heading", name="Sign in to DeviceMesh")).to_be_visible()
        page.get_by_label("Username").fill("operator")
        page.get_by_label("Password").fill("correct-horse")
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.wait_for_url(re.compile(r"/#/$"))
        expect(page.get_by_role("button", name="Sign out")).to_be_visible()

        page.get_by_role("link", name="Services", exact=True).click()
        expect(page.get_by_role("heading", name="Services", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name=re.compile(r"Payments API"))).to_be_visible()
        search_services = page.get_by_label("Search services")
        search_services.fill("payments")
        expect(page.get_by_role("button", name=re.compile(r"Payments API"))).to_be_visible()
        search_services.fill("does-not-exist")
        expect(page.get_by_role("button", name=re.compile(r"Payments API"))).to_have_count(0)
        search_services.fill("")

        page.get_by_role("link", name="Maintenance", exact=True).click()
        page.wait_for_url(re.compile(r"/#/maintenance$"))
        expect(page.get_by_role("heading", name="Maintenance", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Maintenance window", exact=True)).to_be_visible()

        page.get_by_role("link", name="Operations", exact=True).first.click()
        page.wait_for_url(re.compile(r"/#/operations$"))
        expect(page.get_by_role("heading", name="Remote Operations", exact=True)).to_be_visible()
        operation_select = page.get_by_role("combobox", name="Operation")
        operation_select.select_option("network.dns_lookup")
        expect(page.get_by_label("Hostname")).to_be_visible()
        operation_select.select_option("network.route_snapshot")
        expect(page.get_by_label("Hostname")).to_have_count(0)

        page.get_by_role("link", name="Synthetics", exact=True).first.click()
        page.wait_for_url(re.compile(r"/#/synthetics$"))
        expect(page.get_by_role("heading", name="Synthetic Monitoring", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Synthetic monitors", exact=True)).to_be_visible()

        page.get_by_role("link", name="Probes", exact=True).first.click()
        page.wait_for_url(re.compile(r"/#/probes$"))
        expect(page.get_by_role("heading", name="Distributed Probes", exact=True)).to_be_visible()

        page.get_by_role("link", name="Incidents", exact=True).click()
        page.keyboard.press("Control+K")
        global_search = page.get_by_label("Search devices, services and incidents")
        expect(global_search).to_be_focused()
        global_search.fill("database outage")
        incident_result = page.get_by_role("button", name=re.compile(r"Database outage"))
        expect(incident_result).to_be_visible()
        incident_result.click()

        page.wait_for_url(re.compile(r"/#/incidents/inc-1$"))
        expect(page.get_by_role("heading", name="Database outage", exact=True)).to_be_visible()
        expect(page.get_by_text("SEV1 · investigating · assigned to on-call")).to_be_visible()
        expect(page.get_by_text("All incidents", exact=True)).to_be_visible()

        page.get_by_role("button", name="Sign out").click()
        page.wait_for_url(re.compile(r"/#/login$"))
        expect(page.get_by_role("heading", name="Sign in to DeviceMesh")).to_be_visible()

        browser.close()


if __name__ == "__main__":
    main()
