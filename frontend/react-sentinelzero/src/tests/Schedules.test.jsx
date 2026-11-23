import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../contexts/ToastContext'
import Schedules from '../pages/Schedules'
import axios from 'axios'

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

const Wrapper = ({ children }) => (
  <MemoryRouter>
    <ToastProvider>{children}</ToastProvider>
  </MemoryRouter>
)

describe('Schedules', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    axios.get.mockImplementation((url) => {
      if (url.includes('/scheduled-scans/maintenance')) {
        return Promise.resolve({ data: { jobs: [{ id: 'wal_checkpoint', trigger: 'interval', nextRunTime: null }] } })
      }
      if (url.includes('/scheduled-scans')) {
        return Promise.resolve({
          data: {
            jobs: [{
              id: 'nmap_1',
              enabled: true,
              scanType: 'Discovery Scan',
              targetNetwork: '172.16.0.0/22',
              minute: '0',
              hour: '2',
              day: '*',
              month: '*',
              dayOfWeek: '*',
              nextRunTime: null,
            }],
            count: 1,
          },
        })
      }
      if (url.includes('/hunter/timers')) {
        return Promise.resolve({
          data: {
            timers: [{
              name: 'lab_inventory',
              unit: 'sentinel-hunter@lab_inventory.timer',
              label: 'Lab Inventory',
              description: 'Daily lab',
              enabled: true,
              active: true,
              activeState: 'active',
              unitFileState: 'enabled',
              onCalendar: '*-*-* 02:00:00',
              time: '02:00',
            }],
          },
        })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renders schedule board sections', async () => {
    render(<Schedules />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText(/Nmap Scheduled Scans/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Hunter Timers/i)).toBeInTheDocument()
    expect(screen.getByText(/Pivot \/ On-demand/i)).toBeInTheDocument()
    expect(screen.getByText(/Maintenance/i)).toBeInTheDocument()
    expect(screen.getByText(/Lab Inventory/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Discovery Scan')).toBeInTheDocument()
  })
})
