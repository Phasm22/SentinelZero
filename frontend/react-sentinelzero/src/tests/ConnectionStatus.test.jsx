import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import ConnectionStatus from '../components/ConnectionStatus'
import { SocketProvider } from '../contexts/SocketContext'
import { apiService } from '../utils/api'

// Mock the API service
vi.mock('../utils/api', () => ({
  apiService: {
    ping: vi.fn()
  }
}))

// Mock socket.io-client
vi.mock('socket.io-client', () => ({
  io: vi.fn(() => ({
    on: vi.fn(),
    close: vi.fn(),
    connected: true
  }))
}))

const MockedConnectionStatus = () => (
  <SocketProvider>
    <ConnectionStatus />
  </SocketProvider>
)

describe('ConnectionStatus Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render frontend and backend status indicators', async () => {
    // Mock successful API response
    apiService.ping.mockResolvedValue({ status: 'success' })

    render(<MockedConnectionStatus />)

    // Wait for the component to render and API call to complete
    await waitFor(() => {
      expect(screen.getByText(/Frontend/)).toBeInTheDocument()
      expect(screen.getByText(/Backend/)).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('should show connecting state initially', () => {
    apiService.ping.mockImplementation(() => new Promise(() => {})) // Never resolves

    render(<MockedConnectionStatus />)

    expect(screen.getByText(/Frontend Connecting/)).toBeInTheDocument()
    expect(screen.getByText(/Backend Connecting/)).toBeInTheDocument()
  })

  it('should show backend offline when API fails', async () => {
    apiService.ping.mockRejectedValue(new Error('API Error'))

    render(<MockedConnectionStatus />)

    await waitFor(() => {
      expect(screen.getByText(/Backend Offline/)).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('should show backend online when API succeeds', async () => {
    apiService.ping.mockResolvedValue({ status: 'success' })

    render(<MockedConnectionStatus />)

    await waitFor(() => {
      expect(screen.getByText(/Backend Online/)).toBeInTheDocument()
    }, { timeout: 5000 })
  })
})
