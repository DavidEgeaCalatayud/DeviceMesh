import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { EcosystemPage } from '../features/platform/EcosystemPage'
import { platformApi } from '../shared/api/session'

vi.mock('../shared/api/session', () => ({ platformApi: vi.fn() }))

it('separates software readiness from external acceptance gates', async () => {
  vi.mocked(platformApi).mockResolvedValue({
    generatedAt: new Date().toISOString(),
    softwareComplete: true,
    overallStatus: 'software_ready_external_acceptance_pending',
    components: [
      { id: 'backend-api', label: 'Backend API', softwareStatus: 'ready', acceptance: 'integrated' },
      { id: 'esp32', label: 'ESP32 hardware probe', softwareStatus: 'ready', acceptance: 'external_evidence_required' },
    ],
    externalGates: [
      { id: 'long-soak', label: 'Retained 24/48-hour sustained soak', status: 'external_evidence_required' },
    ],
    runtime: { devices: 12, onlineDevices: 10 },
  })
  render(<EcosystemPage />)
  expect(await screen.findByText('Software complete')).toBeInTheDocument()
  expect(screen.getByText('ESP32 hardware probe')).toBeInTheDocument()
  expect(screen.getByText('Retained 24/48-hour sustained soak')).toBeInTheDocument()
  expect(screen.getByText('12')).toBeInTheDocument()
})
