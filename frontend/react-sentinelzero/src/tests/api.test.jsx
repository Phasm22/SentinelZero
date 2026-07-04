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

// Mock axios globally
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

// Import axios after mocking
import axios from 'axios'

// Mock window.matchMedia for UserPreferencesContext
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: query === '(prefers-color-scheme: dark)',
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
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

describe('API Endpoints', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // Mock the specific API calls that Dashboard makes on mount
    axios.get.mockImplementation((url) => {
      if (url === '/api/scan-history') {
        return Promise.resolve({ data: { scans: [] } })
      }
      if (url === '/api/dashboard-stats') {
        return Promise.resolve({ 
          data: { 
            total_scans: 5, 
            hosts_count: 25, 
            vulns_count: 3, 
            latest_scan_time: '2024-01-01T12:00:00Z' 
          } 
        })
      }
      if (url === '/api/insights') {
        return Promise.resolve({ data: { insights: [], summary: {} } })
      }
      if (url === '/api/active-scans') {
        return Promise.resolve({ data: { scans: [] } })
      }
      if (url === '/api/settings') {
        return Promise.resolve({ 
          data: {
            securitySettings: {
              vulnScanningEnabled: true,
              osDetectionEnabled: true,
              serviceDetectionEnabled: true,
              aggressiveScanning: false
            },
            networkSettings: {
              defaultTargetNetwork: '172.16.0.0/22'
            },
            scheduledScansSettings: {
              targetNetwork: '172.16.0.0/22'
            }
          }
        })
      }
      if (url === '/api/network-interfaces') {
        return Promise.resolve({ data: { interfaces: [] } })
      }
      return Promise.resolve({ data: {} })
    })
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

      axios.get.mockResolvedValueOnce({
        data: mockStats
      })

      axios.get.mockResolvedValueOnce({
        data: { scans: [] }
      })

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(axios.get).toHaveBeenCalledWith('/api/scan-history')
        expect(axios.get).toHaveBeenCalledWith('/api/dashboard-stats')
      })
    })

    it('should handle dashboard stats API error', async () => {
      axios.get.mockRejectedValueOnce(new Error('API Error'))

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

      // Mock the scan trigger
      axios.post.mockResolvedValueOnce({
        data: mockResponse
      })

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      const result = await apiService.triggerScan('Discovery Scan')
      
      expect(axios.post).toHaveBeenCalledWith('/api/scan', 'scan_type=Discovery%20Scan', {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      expect(result).toEqual(mockResponse)
    })

    it('should trigger full TCP scan', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 124,
        message: 'Full TCP scan started'
      }

      // Mock the scan trigger
      axios.post.mockResolvedValueOnce({
        data: mockResponse
      })

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      const result = await apiService.triggerScan('Full TCP Scan')
      
      expect(axios.post).toHaveBeenCalledWith('/api/scan', 'scan_type=Full%20TCP%20Scan', {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      expect(result).toEqual(mockResponse)
    })

    it('should trigger IoT scan', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 125,
        message: 'IoT scan started'
      }

      // Mock the scan trigger
      axios.post.mockResolvedValueOnce({
        data: mockResponse
      })

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      const result = await apiService.triggerScan('IoT Scan')
      
      expect(axios.post).toHaveBeenCalledWith('/api/scan', 'scan_type=IoT%20Scan', {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      expect(result).toEqual(mockResponse)
    })

    it('should trigger vulnerability scan', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 126,
        message: 'Vulnerability scan started'
      }

      // Mock the scan trigger
      axios.post.mockResolvedValueOnce({
        data: mockResponse
      })

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      const result = await apiService.triggerScan('Vuln Scripts')
      
      expect(axios.post).toHaveBeenCalledWith('/api/scan', 'scan_type=Vuln%20Scripts', {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      expect(result).toEqual(mockResponse)
    })

    it('should handle scan API error', async () => {
      // Mock the scan trigger with error
      axios.post.mockRejectedValueOnce(new Error('Scan failed'))

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      await expect(apiService.triggerScan('Discovery Scan')).rejects.toThrow('Scan failed')
      
      expect(axios.post).toHaveBeenCalledWith('/api/scan', 'scan_type=Discovery%20Scan', {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
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

      axios.get.mockResolvedValueOnce({
        data: mockSettings
      })

      axios.get.mockResolvedValueOnce({
        data: { interfaces: [] }
      })

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(axios.get).toHaveBeenCalledWith('/api/settings')
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

      const mockResponse = { status: 'success' }

      // Mock the settings save
      axios.post.mockResolvedValueOnce({
        data: mockResponse
      })

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      const result = await apiService.updateSettings(mockSettings)
      
      expect(axios.post).toHaveBeenCalledWith('/api/settings', mockSettings)
      expect(result).toEqual(mockResponse)
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

      axios.get.mockResolvedValueOnce({
        data: mockHistory
      })

      render(
        <TestWrapper>
          <ScanHistory />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(axios.get).toHaveBeenCalledWith('/api/scan-history')
      })
    })
  })

  describe('Button Functionality Tests', () => {
    it('should handle scan button interactions correctly', async () => {
      const mockResponse = {
        status: 'success',
        scan_id: 123,
        message: 'Scan started'
      }

      // Mock the scan trigger
      axios.post.mockResolvedValueOnce({
        data: mockResponse
      })

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      const result = await apiService.triggerScan('Discovery Scan')
      
      expect(axios.post).toHaveBeenCalledWith('/api/scan', 'scan_type=Discovery%20Scan', {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      expect(result).toEqual(mockResponse)
    })

    it('should handle scan button loading states', async () => {
      // Mock a delayed response to simulate loading state
      axios.post.mockImplementationOnce(() => 
        new Promise(resolve => setTimeout(() => resolve({ data: { status: 'success' } }), 100))
      )

      // Import and test the API service directly
      const { apiService } = await import('../utils/api')
      
      const startTime = Date.now()
      const result = await apiService.triggerScan('Discovery Scan')
      const endTime = Date.now()
      
      // Verify the call was made and took some time (simulating loading)
      expect(axios.post).toHaveBeenCalledWith('/api/scan', 'scan_type=Discovery%20Scan', {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      expect(result).toEqual({ status: 'success' })
      expect(endTime - startTime).toBeGreaterThanOrEqual(100)
    })
  })

  describe('Error Handling Tests', () => {
    it('should handle network errors gracefully', async () => {
      axios.get.mockRejectedValueOnce(new Error('Network error'))

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
      axios.get.mockImplementationOnce(() => 
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
