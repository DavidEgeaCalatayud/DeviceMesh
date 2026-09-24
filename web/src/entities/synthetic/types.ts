export type SyntheticMonitorKind = 'http' | 'tcp' | 'icmp'
export type ServiceConsensusClassification = 'healthy' | 'global_outage' | 'regional_degradation' | 'insufficient_data'

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
  failureThreshold: number
  recoveryThreshold: number
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
  probeLocation: string | null
  workId: string | null
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

export interface SyntheticProbe {
  id: string
  name: string
  location: string
  capabilities: SyntheticMonitorKind[]
  enabled: boolean
  lastSeenAt: string | null
  online: boolean
  createdAt: string
  updatedAt: string
}

export interface SyntheticProbeRegistration {
  probe: SyntheticProbe
  token: string
}

export interface SyntheticProbeAssignment {
  monitorId: string
  probeId: string
  enabled: boolean
  nextRunAt: string
  createdAt: string
  updatedAt: string
}

export interface ProbeServiceState {
  probeId: string
  location: string
  success: boolean
  checkedAt: string
  latencyMs: number
}

export interface ServiceConsensus {
  monitorId: string
  generatedAt: string
  classification: ServiceConsensusClassification
  healthyProbes: number
  failingProbes: number
  states: ProbeServiceState[]
}

export interface ServiceIncident {
  id: string
  monitorId: string
  state: 'open' | 'resolved'
  classification: 'service_outage' | 'regional_path'
  openedAt: string
  resolvedAt: string | null
  lastObservedAt: string
  durationSeconds: number
  failureThreshold: number
  recoveryThreshold: number
  maintenanceActiveAtOpen: boolean
  hostOfflineAtOpen: boolean
  failingProbes: number
  totalProbes: number
}

export interface ServiceIncidentSummary {
  monitorId: string
  openIncident: ServiceIncident | null
  incidents: ServiceIncident[]
  resolvedCount: number
  meanRecoverySeconds: number | null
}
