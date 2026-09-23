import type { Device } from '../../entities/device/types'
import type { DeviceEvent } from '../../entities/event/types'

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
