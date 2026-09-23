export type EventSeverity = 'info' | 'warning' | 'critical'

export interface DeviceEvent {
  deviceId: string
  name: string
  timestamp: string
  severity: EventSeverity
  attributes: Record<string, unknown>
}
