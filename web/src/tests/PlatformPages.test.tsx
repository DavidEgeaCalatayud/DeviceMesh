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
    vi.mocked(platformApi).mockImplementation(async path => {
      if (path === '/auth/me') return { role: 'viewer' }
      if (path.endsWith('/rca')) return {
        incidentId: 'one', method: 'dependency-temporal-evidence-v1', status: 'insufficient_data',
        primaryCandidate: null, candidates: [], limitations: ['Correlation is evidence, not proof of causation.'],
      }
      return {
        id: 'one', title: 'API unavailable', severity: 'SEV1', status: 'open', openedAt: new Date().toISOString(),
        assignedTo: null, rootCause: '', resolution: '', impactSummary: '', postmortem: '', timeline: [],
      }
    })
    render(<IncidentsPage incidentId="one" />)
    expect(await screen.findByRole('heading', { name: 'API unavailable' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save incident' })).not.toBeInTheDocument()
  })
  it('renders explainable RCA evidence for an incident', async () => {
    vi.mocked(platformApi).mockImplementation(async path => {
      if (path === '/auth/me') return { role: 'operator' }
      if (path.endsWith('/rca')) return {
        incidentId: 'one', method: 'dependency-temporal-evidence-v1', status: 'explained',
        primaryCandidate: {
          kind: 'service', entityId: 'db', label: 'Orders Database', score: 82, confidence: 'high',
          causalPath: ['Orders Database', 'Checkout API'], firstSignalAt: new Date().toISOString(),
          evidence: [{ kind: 'correlated_incident', summary: 'Database outage preceded the incident', weight: 30, timestamp: new Date().toISOString() }],
        },
        candidates: [], limitations: ['Correlation is evidence, not proof of causation.'],
      }
      return {
        id: 'one', title: 'Checkout unavailable', severity: 'SEV1', status: 'investigating',
        openedAt: new Date().toISOString(), assignedTo: 'sre', rootCause: '', resolution: '',
        impactSummary: '', postmortem: '', timeline: [],
      }
    })
    render(<IncidentsPage incidentId="one" />)
    expect(await screen.findByRole('heading', { name: 'Root cause analysis' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Primary candidate: Orders Database' })).toBeInTheDocument()
    expect(screen.getByText(/Orders Database → Checkout API/)).toBeInTheDocument()
  })

})
