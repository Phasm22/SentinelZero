import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { UserPreferencesProvider } from '../contexts/UserPreferencesContext'
import { ToastProvider } from '../contexts/ToastContext'
import { SocketProvider } from '../contexts/SocketContext'
import HunterRuns from '../pages/HunterRuns'
import axios from 'axios'

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('socket.io-client', () => ({
  default: vi.fn(() => ({ on: vi.fn(), off: vi.fn(), emit: vi.fn(), connected: true })),
  io: vi.fn(() => ({ on: vi.fn(), off: vi.fn(), emit: vi.fn(), connected: true })),
}))

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
})

const Wrapper = ({ children }) => (
  <MemoryRouter>
    <UserPreferencesProvider>
      <ToastProvider>
        <SocketProvider>{children}</SocketProvider>
      </ToastProvider>
    </UserPreferencesProvider>
  </MemoryRouter>
)

describe('HunterRuns', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    axios.get.mockImplementation((url) => {
      if (url.includes('hunter/overview')) {
        return Promise.resolve({ data: { runs: [], meta: { run_count: 0 } } })
      }
      if (url.includes('hunter/missions')) {
        return Promise.resolve({ data: { missions: [] } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renders empty hunter runs state', async () => {
    render(<HunterRuns />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText(/No hunter runs found/i)).toBeInTheDocument()
    })
  })

  it('shows error when overview fails', async () => {
    axios.get.mockRejectedValueOnce({ response: { data: { error: 'Hunter unavailable' } } })
    render(<HunterRuns />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText(/Hunter unavailable/i)).toBeInTheDocument()
    })
  })
})
