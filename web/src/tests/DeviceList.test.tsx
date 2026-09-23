import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { describe, expect, it } from 'vitest'
import { DeviceList } from '../features/devices/DeviceList'

describe('DeviceList', () => {
  it('renders the empty state', () => {
    render(<DeviceList devices={[]} />)
    expect(screen.getByText(/No devices discovered yet/i)).toBeInTheDocument()
  })
})
