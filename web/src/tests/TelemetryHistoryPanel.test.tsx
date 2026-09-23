import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MetricSeries, NetworkDiagnostic } from '../entities/telemetry/types'
import { DiagnosticSummary, MetricChart } from '../features/telemetry/TelemetryHistoryPanel'

const series: MetricSeries = {
  deviceId: 'device-1',
  name: 'network.latency.ms',
  unit: 'ms',
  start: '2026-09-23T10:00:00Z',
  end: '2026-09-23T11:00:00Z',
  bucketSeconds: 60,
  truncated: false,
  points: [
    { timestamp: '2026-09-23T10:00:00Z', value: 10, minimum: 9, maximum: 11, samples: 2 },
    { timestamp: '2026-09-23T11:00:00Z', value: 20, minimum: 18, maximum: 22, samples: 2 },
  ],
}

const diagnostic: NetworkDiagnostic = {
  deviceId: 'device-1',
  state: 'degraded',
  coverage: 'complete',
  windowStart: '2026-09-23T10:45:00Z',
  windowEnd: '2026-09-23T11:00:00Z',
  method: 'threshold-heuristic-v1',
  approximate: true,
  signals: [{ name: 'network.packet_loss.percent', latest: 2, average: 1.5, unit: 'percent', samples: 4 }],
  reasons: ['Packet loss average 1.5 percent meets the degraded threshold (1).'],
}

describe('Telemetry history surfaces', () => {
  it('renders a time-series chart with the latest value', () => {
    render(<MetricChart series={series} label="Latency" />)
    expect(screen.getByRole('img', { name: 'Latency history' })).toBeTruthy()
    expect(screen.getByText('20.0 ms')).toBeTruthy()
  })

  it('keeps measured signals separate from the heuristic diagnostic', () => {
    render(<DiagnosticSummary diagnostic={diagnostic} />)
    expect(screen.getByText('degraded')).toBeTruthy()
    expect(screen.getByText('2.0%')).toBeTruthy()
    expect(screen.getByText(/threshold-heuristic-v1/)).toBeTruthy()
  })
})
