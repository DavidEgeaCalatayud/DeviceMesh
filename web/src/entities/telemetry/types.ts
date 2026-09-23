export interface MetricSample {
  deviceId: string
  timestamp: string
  name: string
  value: number
  unit: string | null
}
