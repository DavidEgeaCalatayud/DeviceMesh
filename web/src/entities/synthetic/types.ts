export type SyntheticMonitorKind = 'http' | 'tcp' | 'icmp'

export interface SyntheticMonitor {
  id: string
  name: string
  kind: SyntheticMonitorKind
  target: string
  port: number | null
  deviceId: string | null
  intervalSeconds: number
  timeoutSeconds: number
  enabled: boolean
  httpMethod: 'GET' | 'HEAD' | null
  expectedStatus: number | null
  createdBy: string
  createdAt: string
  updatedAt: string
  nextRunAt: string
}

export interface SyntheticCheck {
  id: number
  monitorId: string
  checkedAt: string
  success: boolean
  latencyMs: number
  httpStatus: number | null
  errorKind: string | null
  error: string | null
  probeId: string
}

export interface SyntheticSlaWindow {
  label: string
  windowStart: string
  windowEnd: string
  totalChecks: number
  successfulChecks: number
  failedChecks: number
  availabilityPercent: number | null
  meanLatencyMs: number | null
  p95LatencyMs: number | null
}

export interface SyntheticHealth {
  monitorId: string
  generatedAt: string
  consecutiveFailures: number
  failingSince: string | null
  windows: SyntheticSlaWindow[]
}
