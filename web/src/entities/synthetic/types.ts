export interface SyntheticMonitor {
  id: string
  deviceId: string
  name: string
  monitorType: 'http' | 'tcp' | 'icmp'
  target: string
  port: number | null
  expectedStatusMin: number | null
  expectedStatusMax: number | null
  intervalSeconds: number
  timeoutSeconds: number
  enabled: boolean
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface SyntheticSlaWindow {
  label: string
  windowStart: string
  windowEnd: string
  monitoredSeconds: number
  upSeconds: number
  downtimeSeconds: number
  availabilityPercent: number | null
  outageCount: number
  longestOutageSeconds: number
  latencyAverageMs: number | null
  latencyP50Ms: number | null
  latencyP95Ms: number | null
}

export interface SyntheticOutage {
  startedAt: string
  endedAt: string | null
  active: boolean
  durationSeconds: number
  lastFailureReason: string | null
}

export interface SyntheticHealth {
  monitor: SyntheticMonitor
  generatedAt: string
  currentState: 'up' | 'down' | 'unknown'
  currentOutageSeconds: number
  stale: boolean
  lastObservedAt: string | null
  latestLatencyMs: number | null
  latestHttpStatus: number | null
  latestFailureReason: string | null
  windows: SyntheticSlaWindow[]
  outages: SyntheticOutage[]
}

export interface SyntheticMonitorCreate {
  deviceId: string
  name: string
  monitorType: 'http' | 'tcp' | 'icmp'
  target: string
  port?: number
  expectedStatusMin?: number
  expectedStatusMax?: number
  intervalSeconds: number
  timeoutSeconds: number
}
