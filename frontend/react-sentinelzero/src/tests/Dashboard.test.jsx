import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { UserPreferencesProvider } from '../contexts/UserPreferencesContext'
import { ToastProvider } from '../contexts/ToastContext'
import { SocketProvider } from '../contexts/SocketContext'
import Dashboard from '../pages/Dashboard'
import axios from 'axios'

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
  put: vi.fn(),
}))

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: query === '(prefers-color-scheme: dark)',
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock socket.io
vi.mock('socket.io-client', () => ({
  default: vi.fn(() => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    close: vi.fn(),
    connected: true
  })),
  io: vi.fn(() => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    close: vi.fn(),
    connected: true
  }))
}))

// Test wrapper component
const TestWrapper = ({ children }) => (
  <UserPreferencesProvider>
    <ToastProvider>
      <SocketProvider>
        {children}
      </SocketProvider>
    </ToastProvider>
  </UserPreferencesProvider>
)

describe('Dashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // Mock all the API calls that Dashboard makes
    axios.get.mockImplementation((url) => {
      if (url.includes('/api/scan-history')) {
        return Promise.resolve({ data: { scans: [] } })
      }
      if (url.includes('/api/dashboard-stats')) {
        return Promise.resolve({ 
          data: { 
            total_scans: 5, 
            hosts_count: 25, 
            vulns_count: 3, 
            latest_scan_time: '2024-01-01T12:00:00Z' 
          } 
        })
      }
      if (url.includes('/api/insights')) {
        return Promise.resolve({ data: { insights: [], summary: {} } })
      }
      if (url.includes('/api/active-scans')) {
        return Promise.resolve({ data: { scans: [] } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('should render the dashboard main content', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    )

    // Wait for the dashboard to load
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-main')).toBeInTheDocument()
    })

    // Check if the main content grid is rendered
    expect(screen.getByTestId('dashboard-content-grid')).toBeInTheDocument()
  })

  it('should render the scanning section', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    )

    // Wait for the dashboard to load
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-main')).toBeInTheDocument()
    })

    // Check if the scanning section is rendered
    await waitFor(() => {
      expect(screen.getByTestId('scanning-section')).toBeInTheDocument()
    })
  })

  it('should render scan buttons', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    )

    // Wait for the dashboard to load
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-main')).toBeInTheDocument()
    })

    // Wait for the scanning section to be rendered
    await waitFor(() => {
      expect(screen.getByTestId('scanning-section')).toBeInTheDocument()
    })

    // Check if scan buttons are rendered
    await waitFor(() => {
      expect(screen.getByTestId('scan-discovery-btn')).toBeInTheDocument()
      expect(screen.getByTestId('scan-full-tcp-btn')).toBeInTheDocument()
      expect(screen.getByTestId('scan-iot-btn')).toBeInTheDocument()
      expect(screen.getByTestId('scan-vuln-btn')).toBeInTheDocument()
    })
  })
})
