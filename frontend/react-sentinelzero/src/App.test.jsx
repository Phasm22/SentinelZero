import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { UserPreferencesProvider } from './contexts/UserPreferencesContext'
import { ToastProvider } from './contexts/ToastContext'
import { SocketProvider } from './contexts/SocketContext'
import axios from 'axios'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
}))

// Mock socket.io
vi.mock('socket.io-client', () => ({
  default: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    close: vi.fn(),
    connected: true
  }),
  io: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    close: vi.fn(),
    connected: true
  })
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

describe('App Component', () => {
  it('should render without crashing', () => {
    axios.get.mockResolvedValue({ data: { scans: [] } })
    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )
    
    // App should render without throwing
    expect(document.body).toBeInTheDocument()
  })
}) 
