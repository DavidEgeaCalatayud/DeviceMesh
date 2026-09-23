export interface AlertRule {
  id: number
  metricName: string
  operator: string
  threshold: number
  durationSeconds: number
  enabled: boolean
}

export interface AlertIncident {
  id: number
  ruleId: number
  deviceId: string
  openedAt: string
  closedAt: string | null
  active: boolean
  metricName: string
  operator: string
  threshold: number
  durationSeconds: number
  silenced: boolean
  maintenanceWindowId: number | null
}
