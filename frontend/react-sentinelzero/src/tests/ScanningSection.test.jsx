import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { UserPreferencesProvider } from '../contexts/UserPreferencesContext'
import { ToastProvider } from '../contexts/ToastContext'
import { SocketProvider } from '../contexts/SocketContext'
import ScanningSection from '../components/ScanningSection'

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

describe('ScanningSection Component', () => {
  const mockProps = {
    onRequestScan: vi.fn(),
    isScanning: false,
    scanningType: null,
    scanProgress: null,
    scanStatus: 'idle',
    scanMessage: '',
    isConnected: true,
    onUploadComplete: vi.fn(),
    onUploadError: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render the scanning section', () => {
    render(
      <TestWrapper>
        <ScanningSection {...mockProps} />
      </TestWrapper>
    )

    expect(screen.getByTestId('scanning-section')).toBeInTheDocument()
  })

  it('should render scan buttons', () => {
    render(
      <TestWrapper>
        <ScanningSection {...mockProps} />
      </TestWrapper>
    )

    expect(screen.getByTestId('scan-discovery-btn')).toBeInTheDocument()
    expect(screen.getByTestId('scan-full-tcp-btn')).toBeInTheDocument()
    expect(screen.getByTestId('scan-iot-btn')).toBeInTheDocument()
    expect(screen.getByTestId('scan-vuln-btn')).toBeInTheDocument()
  })

  it('should call onRequestScan when scan button is clicked', async () => {
    render(
      <TestWrapper>
        <ScanningSection {...mockProps} />
      </TestWrapper>
    )

    const discoveryButton = screen.getByTestId('scan-discovery-btn')
    fireEvent.click(discoveryButton)

    expect(mockProps.onRequestScan).toHaveBeenCalledWith('Discovery Scan')
  })
})
