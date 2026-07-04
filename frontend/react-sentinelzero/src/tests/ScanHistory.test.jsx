import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { UserPreferencesProvider } from '../contexts/UserPreferencesContext'
import { ToastProvider } from '../contexts/ToastContext'
import { SocketProvider } from '../contexts/SocketContext'
import ScanHistory from '../pages/ScanHistory'
import axios from 'axios'

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn(), put: vi.fn() },
}))

vi.mock('socket.io-client', () => ({
  default: vi.fn(() => ({ on: vi.fn(), off: vi.fn(), emit: vi.fn(), connect: vi.fn(), disconnect: vi.fn(), connected: true })),
  io: vi.fn(() => ({ on: vi.fn(), off: vi.fn(), emit: vi.fn(), connect: vi.fn(), disconnect: vi.fn(), connected: true })),
}))

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({
    matches: false,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })),
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

describe('ScanHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    axios.get.mockImplementation((url) => {
      if (url.includes('scan-history')) {
        return Promise.resolve({
          data: {
            scans: [
              { id: 1, scan_type: 'Full TCP', status: 'complete', total_hosts: 2, hosts_up: 2, created_at: '2026-01-01T00:00:00' },
            ],
          },
        })
      }
      if (url.includes('sync-status')) {
        return Promise.resolve({ data: { sync_status: { in_sync: true } } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renders scan history table with data', async () => {
    render(<ScanHistory />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getAllByText(/Full TCP/i).length).toBeGreaterThan(0)
    })
  })

  it('shows error state when API fails', async () => {
    axios.get.mockImplementation(() => Promise.reject(new Error('network')))
    render(<ScanHistory />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText(/Failed to load scan history/i)).toBeInTheDocument()
    })
  })
})
