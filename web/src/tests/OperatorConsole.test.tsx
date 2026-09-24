import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../shared/api/client'
import { OperatorConsole } from '../features/operations/OperatorConsole'

vi.mock('../shared/api/client', () => ({
  listMaintenanceWindows: vi.fn().mockResolvedValue([]),
  listSyntheticMonitors: vi.fn().mockResolvedValue([]),
  listRemoteOperations: vi.fn().mockResolvedValue([]),
  createMaintenanceWindow: vi.fn(),
  cancelMaintenanceWindow: vi.fn(),
  queueRemoteOperation: vi.fn().mockResolvedValue({}),
  createSyntheticMonitor: vi.fn(),
  disableSyntheticMonitor: vi.fn(),
}))

describe('OperatorConsole', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
    vi.mocked(api.listMaintenanceWindows).mockResolvedValue([])
    vi.mocked(api.listSyntheticMonitors).mockResolvedValue([])
    vi.mocked(api.listRemoteOperations).mockResolvedValue([])
    vi.mocked(api.queueRemoteOperation).mockResolvedValue({} as never)
  })

  it('exposes only the declarative V1.1 remote operation allowlist', () => {
    render(<OperatorConsole deviceId="device-1" />)

    expect(screen.getByText('Agent health check')).toBeTruthy()
    expect(screen.getByText('Collect telemetry')).toBeTruthy()
    expect(screen.getByText('Refresh inventory')).toBeTruthy()
    expect(screen.queryByText(/shell\.execute/i)).toBeNull()
    expect(screen.queryByText(/powershell/i)).toBeNull()
  })

  it('keeps the operator token runtime-only and queues a typed operation', async () => {
    render(<OperatorConsole deviceId="device-1" />)

    fireEvent.change(screen.getByLabelText('Operator token'), {
      target: { value: 'operator-test-token' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Unlock controls' }))

    const healthButton = await screen.findByRole('button', { name: /Agent health check/i })
    await waitFor(() => expect((healthButton as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(healthButton)

    await waitFor(() => {
      expect(api.queueRemoteOperation).toHaveBeenCalledWith(
        'operator-test-token',
        'device-1',
        'agent.health_check',
      )
    })
    expect(sessionStorage.getItem('devicemesh.operatorToken')).toBe('operator-test-token')
  })
})
