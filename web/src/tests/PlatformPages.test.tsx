import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IncidentsPage, LoginPage } from '../features/platform/PlatformPages'
import { platformApi, signIn } from '../shared/api/session'

vi.mock('../shared/api/session', () => ({ platformApi: vi.fn(), signIn: vi.fn(), getToken: () => 'session' }))

describe('Platform screens', () => {
  beforeEach(() => vi.resetAllMocks())
  it('signs in and navigates after success', async () => {
    vi.mocked(signIn).mockResolvedValue(undefined)
    render(<LoginPage />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'david' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'long-enough-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(signIn).toHaveBeenCalledWith('david', 'long-enough-password'))
    await waitFor(() => expect(window.location.hash).toBe('#/'))
  })
  it('does not offer incident mutations to a viewer', async () => {
    vi.mocked(platformApi).mockImplementation(async path => path === '/auth/me' ? { role: 'viewer' } : {
      id: 'one', title: 'API unavailable', severity: 'SEV1', status: 'open', openedAt: new Date().toISOString(),
      assignedTo: null, rootCause: '', resolution: '', timeline: [],
    })
    render(<IncidentsPage incidentId="one" />)
    expect(await screen.findByRole('heading', { name: 'API unavailable' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save incident' })).not.toBeInTheDocument()
  })
})
