import type { AlertIncident, AlertRule } from '../../entities/alert/types'
import type { Device } from '../../entities/device/types'
import type { DeviceEvent } from '../../entities/event/types'
import type { DeviceService, NetworkTopology } from '../../entities/network/types'
import type { MetricSample, MetricSeries, NetworkDiagnostic } from '../../entities/telemetry/types'

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function listDevices(signal?: AbortSignal): Promise<Device[]> {
  const response = await fetch(`${apiBase}/api/v1/devices`, { signal })
  if (!response.ok) throw new Error(`Device API failed: ${response.status}`)
  return response.json() as Promise<Device[]>
}

export async function listEvents(signal?: AbortSignal, limit = 50): Promise<DeviceEvent[]> {
  const response = await fetch(`${apiBase}/api/v1/events?limit=${limit}`, { signal })
  if (!response.ok) throw new Error(`Event API failed: ${response.status}`)
  return response.json() as Promise<DeviceEvent[]>
}

export async function listLatestTelemetry(signal?: AbortSignal): Promise<MetricSample[]> {
  const response = await fetch(`${apiBase}/api/v1/telemetry/latest`, { signal })
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
  const response = await fetch(`${apiBase}/api/v1/telemetry/history?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Telemetry history API failed: ${response.status}`)
  return response.json() as Promise<MetricSeries>
}

export async function getNetworkDiagnostic(
  deviceId: string,
  windowMinutes = 15,
  signal?: AbortSignal,
): Promise<NetworkDiagnostic> {
  const params = new URLSearchParams({
    deviceId,
    windowMinutes: String(windowMinutes),
  })
  const response = await fetch(`${apiBase}/api/v1/telemetry/network-diagnostics?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Network diagnostics API failed: ${response.status}`)
  return response.json() as Promise<NetworkDiagnostic>
}

export async function listAlerts(signal?: AbortSignal, activeOnly = false): Promise<AlertIncident[]> {
  const response = await fetch(`${apiBase}/api/v1/alerts?activeOnly=${activeOnly}`, { signal })
  if (!response.ok) throw new Error(`Alert API failed: ${response.status}`)
  return response.json() as Promise<AlertIncident[]>
}

export async function listAlertRules(signal?: AbortSignal): Promise<AlertRule[]> {
  const response = await fetch(`${apiBase}/api/v1/alert-rules`, { signal })
  if (!response.ok) throw new Error(`Alert rule API failed: ${response.status}`)
  return response.json() as Promise<AlertRule[]>
}

export async function listServices(signal?: AbortSignal, deviceId?: string): Promise<DeviceService[]> {
  const params = new URLSearchParams({ activeOnly: 'true' })
  if (deviceId) params.set('deviceId', deviceId)
  const response = await fetch(`${apiBase}/api/v1/services?${params.toString()}`, { signal })
  if (!response.ok) throw new Error(`Service inventory API failed: ${response.status}`)
  return response.json() as Promise<DeviceService[]>
}

export async function getNetworkTopology(signal?: AbortSignal): Promise<NetworkTopology> {
  const response = await fetch(`${apiBase}/api/v1/network/topology`, { signal })
  if (!response.ok) throw new Error(`Network topology API failed: ${response.status}`)
  return response.json() as Promise<NetworkTopology>
}
