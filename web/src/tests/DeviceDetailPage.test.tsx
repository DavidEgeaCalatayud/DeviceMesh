import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Device } from '../entities/device/types'
import type { DeviceService } from '../entities/network/types'
import type { MetricSample } from '../entities/telemetry/types'
import { DeviceOverview } from '../features/devices/DeviceDetailPage'

const device: Device = {
  id: 'device-1',
  hostname: 'PC-DAVID',
  ipAddresses: ['192.168.1.32'],
  macAddresses: ['00:11:22:33:44:55'],
  operatingSystem: 'Windows 11',
  operatingSystemVersion: '24H2',
  architecture: 'x64',
  manufacturer: 'Example Vendor',
  status: 'online',
  firstSeen: '2026-09-23T10:00:00Z',
  lastSeen: '2026-09-23T11:00:00Z',
}

const metrics: MetricSample[] = [
  { deviceId: 'device-1', timestamp: '2026-09-23T11:00:00Z', name: 'host.cpu.utilization.percent', value: 17.2, unit: 'percent' },
  { deviceId: 'device-1', timestamp: '2026-09-23T11:00:00Z', name: 'host.memory.utilization.percent', value: 42.1, unit: 'percent' },
  { deviceId: 'device-1', timestamp: '2026-09-23T11:00:00Z', name: 'network.packet_loss.percent', value: 2.5, unit: 'percent' },
]

const services: DeviceService[] = [{
  deviceId: 'device-1',
  port: 443,
  transport: 'tcp',
  name: 'https',
  state: 'open',
  firstSeen: '2026-09-23T10:00:00Z',
  lastSeen: '2026-09-23T11:00:00Z',
  lastChangedAt: '2026-09-23T10:00:00Z',
  source: 'probe',
  networkCidr: '192.168.1.0/24',
}]

describe('DeviceOverview', () => {
  it('renders host identity, live metrics and exposed services', () => {
    render(<DeviceOverview device={device} metrics={metrics} services={services} alerts={[]} events={[]} />)
    expect(screen.getByText('PC-DAVID')).toBeTruthy()
    expect(screen.getByText('192.168.1.32')).toBeTruthy()
    expect(screen.getByText('17.2%')).toBeTruthy()
    expect(screen.getByText('2.5%')).toBeTruthy()
    expect(screen.getByText('https')).toBeTruthy()
    expect(screen.getByText('443/tcp · 192.168.1.0/24')).toBeTruthy()
  })
})
