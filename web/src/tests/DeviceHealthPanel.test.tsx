import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DeviceHealthPanel } from '../features/health/DeviceHealthPanel'

const health = {
  deviceId: 'device-1',
  generatedAt: '2026-09-23T12:00:00Z',
  currentState: 'offline' as const,
  currentOutageSeconds: 3600,
  maintenanceActive: true,
  maintenanceWindowId: 42,
  windows: [
    {
      label: '24h',
      windowStart: '2026-09-22T12:00:00Z',
      windowEnd: '2026-09-23T12:00:00Z',
      monitoredSeconds: 86400,
      onlineSeconds: 82800,
      downtimeSeconds: 3600,
      availabilityPercent: 95.833,
      outageCount: 1,
      longestOutageSeconds: 3600,
      meanRecoverySeconds: null,
    },
    {
      label: '7d',
      windowStart: '2026-09-16T12:00:00Z',
      windowEnd: '2026-09-23T12:00:00Z',
      monitoredSeconds: 604800,
      onlineSeconds: 601200,
      downtimeSeconds: 3600,
      availabilityPercent: 99.405,
      outageCount: 1,
      longestOutageSeconds: 3600,
      meanRecoverySeconds: null,
    },
    {
      label: '30d',
      windowStart: '2026-08-24T12:00:00Z',
      windowEnd: '2026-09-23T12:00:00Z',
      monitoredSeconds: 2592000,
      onlineSeconds: 2588400,
      downtimeSeconds: 3600,
      availabilityPercent: 99.861,
      outageCount: 1,
      longestOutageSeconds: 3600,
      meanRecoverySeconds: null,
    },
  ],
}

const outages = [{
  id: 7,
  deviceId: 'device-1',
  startedAt: '2026-09-23T11:00:00Z',
  endedAt: null,
  durationSeconds: 3600,
  active: true,
  source: 'heartbeat-timeout',
}]

describe('DeviceHealthPanel', () => {
  it('renders SLA windows, current outage and maintenance state', () => {
    render(<DeviceHealthPanel health={health} outages={outages} />)

    expect(screen.getByText('95.833%')).toBeTruthy()
    expect(screen.getByText('99.405%')).toBeTruthy()
    expect(screen.getByText('99.861%')).toBeTruthy()
    expect(screen.getByText('Current outage')).toBeTruthy()
    expect(screen.getByText('maintenance')).toBeTruthy()
    expect(screen.getByText(/window #42/i)).toBeTruthy()
    expect(screen.getByText(/heartbeat-timeout/i)).toBeTruthy()
  })
})
