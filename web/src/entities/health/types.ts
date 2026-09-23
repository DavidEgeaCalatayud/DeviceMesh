export interface SlaWindow {
  label: string
  windowStart: string
  windowEnd: string
  monitoredSeconds: number
  onlineSeconds: number
  downtimeSeconds: number
  availabilityPercent: number | null
  outageCount: number
  longestOutageSeconds: number
  meanRecoverySeconds: number | null
}

export interface DeviceHealth {
  deviceId: string
  generatedAt: string
  currentState: 'online' | 'offline' | null
  currentOutageSeconds: number
  maintenanceActive: boolean
  maintenanceWindowId: number | null
  windows: SlaWindow[]
}

export interface Outage {
  id: number
  deviceId: string
  startedAt: string
  endedAt: string | null
  durationSeconds: number
  active: boolean
  source: string
}

export interface MaintenanceWindow {
  id: number
  deviceId: string | null
  startsAt: string
  endsAt: string
  reason: string
  createdBy: string
  createdAt: string
  cancelledAt: string | null
  active: boolean
}
