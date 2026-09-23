import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Device } from '../entities/device/types'
import type { DeviceService, NetworkTopology } from '../entities/network/types'
import { NetworkPanel } from '../features/network/NetworkPanel'

const device: Device = {
  id: 'device-1',
  hostname: 'PC-DAVID',
  ipAddresses: ['192.168.1.32'],
  macAddresses: ['00:11:22:33:44:55'],
  operatingSystem: 'Windows 11',
  operatingSystemVersion: '24H2',
  architecture: 'x64',
  manufacturer: null,
  status: 'online',
  firstSeen: '2026-09-23T10:00:00Z',
  lastSeen: '2026-09-23T10:01:00Z',
}

const topology: NetworkTopology = {
  approximate: true,
  method: 'observation-segment',
  nodes: [
    { id: 'network:192.168.1.0/24', kind: 'network', label: '192.168.1.0/24', deviceId: null, networkCidr: '192.168.1.0/24', status: null },
    { id: 'device:device-1', kind: 'device', label: 'PC-DAVID', deviceId: 'device-1', networkCidr: '192.168.1.0/24', status: 'online' },
  ],
  edges: [{ source: 'network:192.168.1.0/24', target: 'device:device-1', relation: 'observed-on' }],
}

const services: DeviceService[] = [{
  deviceId: 'device-1',
  port: 443,
  transport: 'tcp',
  name: 'https',
  state: 'open',
  firstSeen: '2026-09-23T10:00:00Z',
  lastSeen: '2026-09-23T10:01:00Z',
  lastChangedAt: '2026-09-23T10:00:00Z',
  source: 'probe',
  networkCidr: '192.168.1.0/24',
}]

describe('NetworkPanel', () => {
  it('renders observed segments, devices and allowed exposed services', () => {
    render(<NetworkPanel topology={topology} services={services} devices={[device]} />)
    expect(screen.getByText('192.168.1.0/24')).toBeTruthy()
    expect(screen.getByText('PC-DAVID')).toBeTruthy()
    expect(screen.getByText('https · 443/tcp')).toBeTruthy()
    expect(screen.getByText(/Approximate/)).toBeTruthy()
  })
})
