import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { UserPreferencesProvider } from '../contexts/UserPreferencesContext'
import { ToastProvider } from '../contexts/ToastContext'
import { SocketProvider } from '../contexts/SocketContext'
import Settings from '../pages/Settings'
import axios from 'axios'

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}))

vi.mock('socket.io-client', () => ({
  default: vi.fn(() => ({ on: vi.fn(), off: vi.fn(), emit: vi.fn(), connected: true })),
  io: vi.fn(() => ({ on: vi.fn(), off: vi.fn(), emit: vi.fn(), connected: true })),
}))

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
})

const defaultSettings = {
  networkSettings: { defaultTargetNetwork: '172.16.0.0/22', concurrentScans: 1, localModeEnabled: false },
  securitySettings: { vulnScanningEnabled: true, osDetectionEnabled: true, serviceDetectionEnabled: true },
  notificationSettings: { pushoverConfigured: false },
  scheduledScansSettings: { enabled: false, scanType: 'Full TCP', targetNetwork: '172.16.0.0/22' },
}

const Wrapper = ({ children }) => (
  <MemoryRouter>
    <UserPreferencesProvider>
      <ToastProvider>
        <SocketProvider>{children}</SocketProvider>
      </ToastProvider>
    </UserPreferencesProvider>
  </MemoryRouter>
)

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    axios.get.mockImplementation((url) => {
      if (url.includes('/api/settings')) {
        return Promise.resolve({ data: defaultSettings })
      }
      if (url.includes('network-interfaces')) {
        return Promise.resolve({ data: { interfaces: [], count: 0 } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renders settings sections', async () => {
    render(<Settings />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getAllByText(/User Preferences|Scheduled Scans|Network Settings/i).length).toBeGreaterThan(0)
    })
  })

  it('shows error when settings load fails', async () => {
    axios.get.mockRejectedValueOnce(new Error('settings failed'))
    render(<Settings />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText(/Failed to load settings/i)).toBeInTheDocument()
    })
  })
})
