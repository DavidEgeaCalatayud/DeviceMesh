import type { AlertIncident, AlertRule } from '../../entities/alert/types'
import type { Device } from '../../entities/device/types'
import type { DeviceEvent } from '../../entities/event/types'
import type { DeviceHealth, MaintenanceWindow, Outage } from '../../entities/health/types'
import type { DeviceService, NetworkTopology } from '../../entities/network/types'
import type { RemoteOperation, RemoteOperationType } from '../../entities/operations/types'
import type { SyntheticCheck, SyntheticHealth, SyntheticMonitor, SyntheticMonitorKind } from '../../entities/synthetic/types'
import type { MetricSample, MetricSeries, NetworkDiagnostic } from '../../entities/telemetry/types'

import { apiBase, apiFetch } from './session'

function operatorHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
}

export async function listDevices(signal?: AbortSignal): Promise<Device[]> {
  const response = await apiFetch(`${apiBase}/api/v1/devices`, { signal })
  if (!response.ok) throw new Error(`Device API failed: ${response.status}`)
  return response.json() as Promise<Device[]>
}

export async function listEvents(signal?: AbortSignal, limit = 50): Promise<DeviceEvent[]> {
  const response = await apiFetch(`${apiBase}/api/v1/events?limit=${limit}`, { signal })
  if (!response.ok) throw new Error(`Event API failed: ${response.status}`)
  return response.json() as Promise<DeviceEvent[]>
}

export async function listLatestTelemetry(signal?: AbortSignal): Promise<MetricSample[]> {
  const response = await apiFetch(`${apiBase}/api/v1/telemetry/latest`, { signal })
  if (!response.ok) throw new Error(`Telemetry API failed: ${response.status}`)
  return response.json() as Promise<MetricSample[]>
}

export async function getMetricHistory(
  deviceId: string,
  name: string,
  start: Date,
  end: Date,
  bucketSeconds: number,
  signal?: AbortSignal,
  resolution: 'raw' | 'hourly' = 'raw',
): Promise<MetricSeries> {
  const params = new URLSearchParams({
    deviceId,
    name,
    start: start.toISOString(),
    end: end.toISOString(),
    bucketSeconds: String(resolution === 'hourly' ? 3600 : bucketSeconds),
    limit: '1200',
    resolution,
  })
  const response = await apiFetch(`${apiBase}/api/v1/telemetry/history?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Telemetry history API failed: ${response.status}`)
  return response.json() as Promise<MetricSeries>
}

export async function getNetworkDiagnostic(
  deviceId: string,
  windowMinutes = 15,
  signal?: AbortSignal,
): Promise<NetworkDiagnostic> {
  const params = new URLSearchParams({ deviceId, windowMinutes: String(windowMinutes) })
  const response = await apiFetch(`${apiBase}/api/v1/telemetry/network-diagnostics?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Network diagnostics API failed: ${response.status}`)
  return response.json() as Promise<NetworkDiagnostic>
}

export async function getDeviceHealth(deviceId: string, signal?: AbortSignal): Promise<DeviceHealth> {
  const response = await apiFetch(`${apiBase}/api/v1/devices/${encodeURIComponent(deviceId)}/health`, { signal })
  if (!response.ok) throw new Error(`Device health API failed: ${response.status}`)
  return response.json() as Promise<DeviceHealth>
}

export async function getDeviceOutages(deviceId: string, days = 30, signal?: AbortSignal): Promise<Outage[]> {
  const params = new URLSearchParams({ days: String(days), limit: '100' })
  const response = await apiFetch(`${apiBase}/api/v1/devices/${encodeURIComponent(deviceId)}/outages?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Device outage API failed: ${response.status}`)
  return response.json() as Promise<Outage[]>
}

export async function listMaintenanceWindows(signal?: AbortSignal, deviceId?: string, activeOnly = false): Promise<MaintenanceWindow[]> {
  const params = new URLSearchParams({ activeOnly: String(activeOnly), limit: '100' })
  if (deviceId) params.set('deviceId', deviceId)
  const response = await apiFetch(`${apiBase}/api/v1/maintenance-windows?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Maintenance API failed: ${response.status}`)
  return response.json() as Promise<MaintenanceWindow[]>
}

export async function createMaintenanceWindow(
  token: string,
  input: { deviceId: string | null; startsAt: string; endsAt: string; reason: string },
): Promise<MaintenanceWindow> {
  const response = await apiFetch(`${apiBase}/api/v1/operator/maintenance-windows`, {
    method: 'POST',
    headers: operatorHeaders(token),
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(`Create maintenance failed: ${response.status}`)
  return response.json() as Promise<MaintenanceWindow>
}

export async function cancelMaintenanceWindow(token: string, windowId: number): Promise<MaintenanceWindow> {
  const response = await apiFetch(`${apiBase}/api/v1/operator/maintenance-windows/${windowId}/cancel`, {
    method: 'POST',
    headers: operatorHeaders(token),
  })
  if (!response.ok) throw new Error(`Cancel maintenance failed: ${response.status}`)
  return response.json() as Promise<MaintenanceWindow>
}

export async function listRemoteOperations(token: string, deviceId?: string): Promise<RemoteOperation[]> {
  const params = new URLSearchParams({ limit: '100' })
  if (deviceId) params.set('deviceId', deviceId)
  const response = await apiFetch(`${apiBase}/api/v1/operator/remote-operations?${params.toString()}`, {
    headers: operatorHeaders(token),
  })
  if (!response.ok) throw new Error(`Remote operation API failed: ${response.status}`)
  return response.json() as Promise<RemoteOperation[]>
}

export async function queueRemoteOperation(token: string, deviceId: string, operationType: RemoteOperationType): Promise<RemoteOperation> {
  const response = await apiFetch(`${apiBase}/api/v1/operator/remote-operations`, {
    method: 'POST',
    headers: operatorHeaders(token),
    body: JSON.stringify({ deviceId, operationType, arguments: {}, ttlSeconds: 300 }),
  })
  if (!response.ok) throw new Error(`Queue remote operation failed: ${response.status}`)
  return response.json() as Promise<RemoteOperation>
}

export async function listSyntheticMonitors(signal?: AbortSignal, deviceId?: string): Promise<SyntheticMonitor[]> {
  const params = new URLSearchParams()
  if (deviceId) params.set('deviceId', deviceId)
  const suffix = params.size ? `?${params.toString()}` : ''
  const response = await apiFetch(`${apiBase}/api/v1/synthetic-monitors${suffix}`, { signal })
  if (!response.ok) throw new Error(`Synthetic monitor API failed: ${response.status}`)
  return response.json() as Promise<SyntheticMonitor[]>
}

export async function createSyntheticMonitor(
  token: string,
  input: {
    name: string
    kind: SyntheticMonitorKind
    target: string
    port: number | null
    deviceId: string | null
    intervalSeconds: number
    timeoutSeconds: number
    httpMethod: 'GET' | 'HEAD' | null
    expectedStatus: number | null
    httpHeaders: Record<string, string>
    httpSecretHeaders: Record<string, string>
    expectedBodyContains: string | null
  },
): Promise<SyntheticMonitor> {
  const response = await apiFetch(`${apiBase}/api/v1/operator/synthetic-monitors`, {
    method: 'POST',
    headers: operatorHeaders(token),
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(`Create synthetic monitor failed: ${response.status}`)
  return response.json() as Promise<SyntheticMonitor>
}

export async function setSyntheticMonitorEnabled(token: string, monitorId: string, enabled: boolean): Promise<SyntheticMonitor> {
  const response = await apiFetch(`${apiBase}/api/v1/operator/synthetic-monitors/${encodeURIComponent(monitorId)}/state`, {
    method: 'PATCH',
    headers: operatorHeaders(token),
    body: JSON.stringify({ enabled }),
  })
  if (!response.ok) throw new Error(`Update synthetic monitor failed: ${response.status}`)
  return response.json() as Promise<SyntheticMonitor>
}

export async function getSyntheticHealth(monitorId: string, signal?: AbortSignal): Promise<SyntheticHealth> {
  const response = await apiFetch(`${apiBase}/api/v1/synthetic-monitors/${encodeURIComponent(monitorId)}/health`, { signal })
  if (!response.ok) throw new Error(`Synthetic health API failed: ${response.status}`)
  return response.json() as Promise<SyntheticHealth>
}

export async function getSyntheticResults(monitorId: string, signal?: AbortSignal): Promise<SyntheticCheck[]> {
  const response = await apiFetch(`${apiBase}/api/v1/synthetic-monitors/${encodeURIComponent(monitorId)}/results?limit=50`, { signal })
  if (!response.ok) throw new Error(`Synthetic results API failed: ${response.status}`)
  return response.json() as Promise<SyntheticCheck[]>
}

export async function listAlerts(signal?: AbortSignal, activeOnly = false): Promise<AlertIncident[]> {
  const response = await apiFetch(`${apiBase}/api/v1/alerts?activeOnly=${activeOnly}`, { signal })
  if (!response.ok) throw new Error(`Alert API failed: ${response.status}`)
  return response.json() as Promise<AlertIncident[]>
}

export async function listAlertRules(signal?: AbortSignal): Promise<AlertRule[]> {
  const response = await apiFetch(`${apiBase}/api/v1/alert-rules`, { signal })
  if (!response.ok) throw new Error(`Alert rule API failed: ${response.status}`)
  return response.json() as Promise<AlertRule[]>
}

export async function listServices(signal?: AbortSignal, deviceId?: string): Promise<DeviceService[]> {
  const params = new URLSearchParams({ activeOnly: 'true' })
  if (deviceId) params.set('deviceId', deviceId)
  const response = await apiFetch(`${apiBase}/api/v1/services?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Service inventory API failed: ${response.status}`)
  return response.json() as Promise<DeviceService[]>
}

export async function getNetworkTopology(signal?: AbortSignal): Promise<NetworkTopology> {
  const response = await apiFetch(`${apiBase}/api/v1/network/topology`, { signal })
  if (!response.ok) throw new Error(`Network topology API failed: ${response.status}`)
  return response.json() as Promise<NetworkTopology>
}
