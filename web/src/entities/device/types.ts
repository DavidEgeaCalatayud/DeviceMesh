export type DeviceStatus = 'online' | 'offline' | 'unknown'

export interface Device {
  id: string
  hostname: string | null
  ipAddresses: string[]
  macAddresses: string[]
  operatingSystem: string | null
  status: DeviceStatus
  firstSeen: string | null
  lastSeen: string | null
}
