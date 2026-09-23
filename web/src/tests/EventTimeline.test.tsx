import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EventTimeline } from '../features/events/EventTimeline'

const events = [
  {
    deviceId: 'pc-david',
    name: 'DEVICE_ONLINE',
    timestamp: '2026-09-23T12:00:00Z',
    severity: 'info' as const,
    attributes: { hostname: 'PC-DAVID' },
  },
  {
    deviceId: 'pc-david',
    name: 'ALERT_OPENED',
    timestamp: '2026-09-23T12:01:00Z',
    severity: 'warning' as const,
    attributes: { hostname: 'PC-DAVID', metricName: 'system.cpu.percent' },
  },
]

describe('EventTimeline', () => {
  it('filters alert events without losing the persisted timeline state', () => {
    render(<EventTimeline events={events} />)

    expect(screen.getByText(/PC-DAVID online/i)).toBeTruthy()
    expect(screen.getByText(/PC-DAVID alert opened/i)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Alerts' }))
    expect(screen.queryByText(/PC-DAVID online/i)).toBeNull()
    expect(screen.getByText(/PC-DAVID alert opened/i)).toBeTruthy()
  })

  it('searches by device and event attributes', () => {
    render(<EventTimeline events={events} />)

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search timeline' }), {
      target: { value: 'cpu' },
    })

    expect(screen.queryByText(/PC-DAVID online/i)).toBeNull()
    expect(screen.getByText(/PC-DAVID alert opened/i)).toBeTruthy()
  })
})
