import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SyntheticHealth } from '../entities/synthetic/types'
import { ServiceHealthPanel } from '../features/health/ServiceHealthPanel'

const service: SyntheticHealth = {
  monitor: {
    id: 'monitor-1',
    deviceId: 'device-1',
    name: 'Public API',
    monitorType: 'http',
    target: 'https://example.com/health',
    port: null,
    expectedStatusMin: 200,
    expectedStatusMax: 399,
    intervalSeconds: 60,
    timeoutSeconds: 5,
    enabled: true,
    createdBy: 'operator',
    createdAt: '2026-09-24T06:00:00Z',
    updatedAt: '2026-09-24T06:00:00Z',
  },
  generatedAt: '2026-09-24T07:00:00Z',
  currentState: 'down',
  currentOutageSeconds: 90,
  stale: false,
  lastObservedAt: '2026-09-24T06:59:30Z',
  latestLatencyMs: 185.4,
  latestHttpStatus: 503,
  latestFailureReason: 'http_status_503',
  windows: [
    {
      label: '24h',
      windowStart: '2026-09-23T07:00:00Z',
      windowEnd: '2026-09-24T07:00:00Z',
      monitoredSeconds: 3600,
      upSeconds: 3540,
      downtimeSeconds: 60,
      availabilityPercent: 98.333,
      outageCount: 1,
      longestOutageSeconds: 60,
      latencyAverageMs: 42,
      latencyP50Ms: 38,
      latencyP95Ms: 85,
    },
  ],
  outages: [
    {
      startedAt: '2026-09-24T06:58:30Z',
      endedAt: null,
      active: true,
      durationSeconds: 90,
      lastFailureReason: 'http_status_503',
    },
  ],
}

describe('ServiceHealthPanel', () => {
  it('renders externally observed service state separately from agent health', () => {
    render(<ServiceHealthPanel services={[service]} />)

    expect(screen.getByText('Service health')).toBeTruthy()
    expect(screen.getByText('External synthetic availability')).toBeTruthy()
    expect(screen.getByText('Public API')).toBeTruthy()
    expect(screen.getByText('https://example.com/health')).toBeTruthy()
    expect(screen.getByText('503')).toBeTruthy()
    expect(screen.getByText('98.333%')).toBeTruthy()
    expect(screen.getAllByText('http_status_503').length).toBeGreaterThan(0)
  })
})
