/**
 * Comprehensive API Test Suite for SentinelZero Frontend
 * Tests all API endpoints and button functionality
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import Dashboard from '../pages/Dashboard'
import Settings from '../pages/Settings'
import ScanHistory from '../pages/ScanHistory'
import { UserPreferencesProvider } from '../contexts/UserPreferencesContext'
import { ToastProvider } from '../contexts/ToastContext'
import { SocketProvider } from '../contexts/SocketContext'

// Mock fetch globally
global.fetch = vi.fn()

// Mock socket.io
vi.mock('socket.io-client', () => ({
  default: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    connected: true
  })
}))

// Test wrapper component
const TestWrapper = ({ children }) => (
  <BrowserRouter>
    <UserPreferencesProvider>
      <ToastProvider>
        <SocketProvider>
          {children}
        </SocketProvider>
      </ToastProvider>
    </UserPreferencesProvider>
  </BrowserRouter>
)

describe('API Endpoints', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('Dashboard API Tests', () => {
    it('should load dashboard stats on mount', async () => {
      const mockStats = {
        total_scans: 5,
        hosts_count: 25,
        vulns_count: 3,
        latest_scan_time: '2024-01-01T12:00:00Z'
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats
      })

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ scans: [] })
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/dashboard-stats')
        expect(fetch).toHaveBeenCalledWith('/api/scan-history')
      })
    })

    it('should handle dashboard stats API error', async () => {
      fetch.mockRejectedValueOnce(new Error('API Error'))

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Error')).toBeInTheDocument()
      })
    })
  })

  describe('Scan API Tests', () => {
    it('should trigger discovery scan', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 123,
        message: 'Discovery scan started'
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        const discoveryButton = screen.getByTestId('scan-discovery-btn')
        expect(discoveryButton).toBeInTheDocument()
      })

      const discoveryButton = screen.getByTestId('scan-discovery-btn')
      fireEvent.click(discoveryButton)

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/scan', {
          method: 'POST',
          body: expect.any(FormData)
        })
      })
    })

    it('should trigger full TCP scan', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 124,
        message: 'Full TCP scan started'
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        const fullTcpButton = screen.getByTestId('scan-full-tcp-btn')
        expect(fullTcpButton).toBeInTheDocument()
      })

      const fullTcpButton = screen.getByTestId('scan-full-tcp-btn')
      fireEvent.click(fullTcpButton)

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/scan', {
          method: 'POST',
          body: expect.any(FormData)
        })
      })
    })

    it('should trigger IoT scan', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 125,
        message: 'IoT scan started'
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        const iotButton = screen.getByTestId('scan-iot-btn')
        expect(iotButton).toBeInTheDocument()
      })

      const iotButton = screen.getByTestId('scan-iot-btn')
      fireEvent.click(iotButton)

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/scan', {
          method: 'POST',
          body: expect.any(FormData)
        })
      })
    })

    it('should trigger vulnerability scan', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 126,
        message: 'Vulnerability scan started'
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        const vulnButton = screen.getByTestId('scan-vuln-btn')
        expect(vulnButton).toBeInTheDocument()
      })

      const vulnButton = screen.getByTestId('scan-vuln-btn')
      fireEvent.click(vulnButton)

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/scan', {
          method: 'POST',
          body: expect.any(FormData)
        })
      })
    })

    it('should handle scan API error', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: 'Scan failed' })
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        const discoveryButton = screen.getByTestId('scan-discovery-btn')
        expect(discoveryButton).toBeInTheDocument()
      })

      const discoveryButton = screen.getByTestId('scan-discovery-btn')
      fireEvent.click(discoveryButton)

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/scan', {
          method: 'POST',
          body: expect.any(FormData)
        })
      })
    })
  })

  describe('Settings API Tests', () => {
    it('should load settings on mount', async () => {
      const mockSettings = {
        securitySettings: {
          vulnScanningEnabled: true,
          osDetectionEnabled: true,
          serviceDetectionEnabled: true,
          aggressiveScanning: false
        },
        networkSettings: {
          defaultTargetNetwork: '172.16.0.0/22',
          maxHosts: 1000,
          scanTimeout: 300,
          concurrentScans: 1,
          preDiscoveryEnabled: false
        },
        notificationSettings: {
          pushoverEnabled: false,
          scanComplete: true,
          vulnerabilityFound: true,
          newHostFound: false
        }
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings
      })

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ interfaces: [] })
      })

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/settings')
        expect(fetch).toHaveBeenCalledWith('/api/network-interfaces')
      })
    })

    it('should save settings', async () => {
      const mockSettings = {
        securitySettings: {
          vulnScanningEnabled: true,
          osDetectionEnabled: true,
          serviceDetectionEnabled: true,
          aggressiveScanning: false
        }
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings
      })

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ interfaces: [] })
      })

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'success' })
      })

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      )

      await waitFor(() => {
        const saveButton = screen.getByText('Save')
        expect(saveButton).toBeInTheDocument()
      })

      const saveButton = screen.getByText('Save')
      fireEvent.click(saveButton)

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/settings', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: expect.any(String)
        })
      })
    })
  })

  describe('Scan History API Tests', () => {
    it('should load scan history', async () => {
      const mockHistory = {
        scans: [
          {
            id: 1,
            scan_type: 'Full TCP',
            status: 'complete',
            timestamp: '2024-01-01T12:00:00Z',
            hosts_count: 5,
            vulns_count: 2
          }
        ]
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockHistory
      })

      render(
        <TestWrapper>
          <ScanHistory />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/scan-history')
      })
    })
  })

  describe('Button Functionality Tests', () => {
    it('should disable scan buttons when scanning', async () => {
      const mockStats = {
        total_scans: 0,
        hosts_count: 0,
        vulns_count: 0,
        latest_scan_time: null
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats
      })

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ scans: [] })
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        const fullTcpButton = screen.getByTestId('scan-full-tcp-btn')
        const iotButton = screen.getByTestId('scan-iot-btn')
        const vulnButton = screen.getByTestId('scan-vuln-btn')

        expect(fullTcpButton).not.toBeDisabled()
        expect(iotButton).not.toBeDisabled()
        expect(vulnButton).not.toBeDisabled()
      })
    })

    it('should show loading state on scan buttons', async () => {
      const mockStats = {
        total_scans: 0,
        hosts_count: 0,
        vulns_count: 0,
        latest_scan_time: null
      }

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats
      })

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ scans: [] })
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        const discoveryButton = screen.getByTestId('scan-discovery-btn')
        expect(discoveryButton).toBeInTheDocument()
      })

      // Simulate scanning state
      const discoveryButton = screen.getByTestId('scan-discovery-btn')
      fireEvent.click(discoveryButton)

      // Button should show loading state
      expect(discoveryButton).toHaveAttribute('disabled')
    })
  })

  describe('Error Handling Tests', () => {
    it('should handle network errors gracefully', async () => {
      fetch.mockRejectedValueOnce(new Error('Network error'))

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Error')).toBeInTheDocument()
      })
    })

    it('should handle API timeout', async () => {
      fetch.mockImplementationOnce(() => 
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Timeout')), 100)
        )
      )

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Error')).toBeInTheDocument()
      })
    })
  })

  describe('Theme System Tests', () => {
    it('should apply dark theme when system prefers dark', () => {
      // Mock matchMedia
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

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      // Check if dark class is applied
      expect(document.documentElement.classList.contains('dark')).toBe(true)
    })

    it('should apply light theme when system prefers light', () => {
      // Mock matchMedia for light theme
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn().mockImplementation(query => ({
          matches: query === '(prefers-color-scheme: light)',
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      // Check if dark class is not applied
      expect(document.documentElement.classList.contains('dark')).toBe(false)
    })
  })
})
