import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AlertPanel } from '../features/alerts/AlertPanel'

const devices = [{
  id: 'device-1',
  hostname: 'PC-DAVID',
  ipAddresses: ['192.168.1.32'],
  macAddresses: [],
  operatingSystem: 'Windows 11',
  operatingSystemVersion: null,
  architecture: 'x64',
  manufacturer: null,
  status: 'online' as const,
  firstSeen: null,
  lastSeen: null,
}]

describe('AlertPanel', () => {
  it('renders an active threshold incident with the device identity', () => {
    render(<AlertPanel devices={devices} alerts={[{
      id: 1,
      ruleId: 7,
      deviceId: 'device-1',
      openedAt: '2026-09-23T12:00:00Z',
      closedAt: null,
      active: true,
      metricName: 'system.cpu.percent',
      operator: '>',
      threshold: 90,
      durationSeconds: 60,
      silenced: false,
      maintenanceWindowId: null,
    }]} />)

    expect(screen.getByText('PC-DAVID')).toBeTruthy()
    expect(screen.getByText(/system.cpu.percent > 90 for 60s/i)).toBeTruthy()
    expect(screen.getByText(/Active incidents/i)).toBeTruthy()
  })

  it('labels an incident silenced by maintenance without hiding it', () => {
    render(<AlertPanel devices={devices} alerts={[{
      id: 2,
      ruleId: 8,
      deviceId: 'device-1',
      openedAt: '2026-09-23T12:00:00Z',
      closedAt: null,
      active: true,
      metricName: 'network.packet_loss.percent',
      operator: '>=',
      threshold: 5,
      durationSeconds: 60,
      silenced: true,
      maintenanceWindowId: 42,
    }]} />)

    expect(screen.getByText('silenced')).toBeTruthy()
    expect(screen.getByText(/Maintenance window #42/i)).toBeTruthy()
    expect(screen.getByText(/network.packet_loss.percent/i)).toBeTruthy()
  })
})
