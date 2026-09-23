export interface MetricSample {
  deviceId: string
  timestamp: string
  name: string
  value: number
  unit: string | null
}

export interface MetricSeriesPoint {
  timestamp: string
  value: number
  minimum: number
  maximum: number
  samples: number
}

export interface MetricSeries {
  deviceId: string
  name: string
  unit: string | null
  start: string
  end: string
  bucketSeconds: number | null
  truncated: boolean
  points: MetricSeriesPoint[]
}

export interface DiagnosticSignal {
  name: string
  latest: number
  average: number
  unit: string | null
  samples: number
}

export interface NetworkDiagnostic {
  deviceId: string
  state: 'healthy' | 'degraded' | 'poor' | 'unknown'
  coverage: 'complete' | 'partial' | 'none'
  windowStart: string
  windowEnd: string
  method: string
  approximate: boolean
  signals: DiagnosticSignal[]
  reasons: string[]
}
