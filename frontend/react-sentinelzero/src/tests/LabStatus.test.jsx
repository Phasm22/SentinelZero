import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LabStatus from '../pages/LabStatus'
import { SocketProvider } from '../contexts/SocketContext'

const socketHandlers = {}
const socketMock = {
  on: vi.fn((event, handler) => {
    socketHandlers[event] = handler
  }),
  off: vi.fn((event) => {
    delete socketHandlers[event]
  }),
  emit: vi.fn(),
  close: vi.fn(),
}

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => socketMock),
}))

const sampleSnapshot = {
  overall_status: 'degraded',
  health_percentage: 66.7,
  total_items: 3,
  up_items: 2,
  down_items: 1,
  total_up: 2,
  total_checks: 3,
  timestamp: '2026-03-08T00:00:00Z',
  last_update: '2026-03-08T00:00:00Z',
  layers: {
    loopbacks: { total: 1, up: 1 },
    services: { total: 1, up: 0 },
    infrastructure: { total: 1, up: 1 },
  },
  categories: {
    loopbacks: { items: [{ name: 'Localhost', ip: '127.0.0.1', status: 'up' }] },
    services: { items: [{ name: 'DNS', ip: '1.1.1.1', overall_status: 'down', status: 'down' }] },
    infrastructure: { items: [{ name: 'Gateway', ip: '172.16.0.1', status: 'up' }] },
  },
}

const renderLabStatus = () => render(
  <SocketProvider>
    <LabStatus />
  </SocketProvider>
)

const hasOperationalCount = (expected) => (_, node) => {
  const text = node?.textContent?.replace(/\s+/g, ' ').trim() || ''
  return text.includes(`${expected} systems operational`) || text.includes(expected)
}

describe('LabStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    for (const key of Object.keys(socketHandlers)) delete socketHandlers[key]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => sampleSnapshot,
    })
  })

  it('renders the summary snapshot from the API', async () => {
    renderLabStatus()

    await waitFor(() => {
      expect(screen.getAllByText((_, node) => {
        const text = node?.textContent?.replace(/\s+/g, ' ').trim() || ''
        return text.includes('2/3') && text.includes('systems operational')
      }).length).toBeGreaterThan(0)
    })

    expect(global.fetch).toHaveBeenCalledWith(`${window.location.origin}/api/whatsup/summary`, expect.any(Object))
    expect(screen.getAllByText(hasOperationalCount('2/3')).length).toBeGreaterThan(0)
    expect(screen.getByText(/Lab Network Overview/i)).toBeInTheDocument()
    expect(screen.getByText(/Host Details/i)).toBeInTheDocument()
  })

  it('applies realtime snapshot updates from the socket', async () => {
    renderLabStatus()

    await waitFor(() => {
      expect(socketHandlers.connect).toBeTypeOf('function')
    })
    socketHandlers.connect()

    await waitFor(() => {
      expect(socketHandlers['whats_up.snapshot']).toBeTypeOf('function')
    })

    socketHandlers['whats_up.snapshot']({
      ...sampleSnapshot,
      total_up: 3,
      total_checks: 3,
      health_percentage: 100,
      layers: {
        loopbacks: { total: 1, up: 1 },
        services: { total: 1, up: 1 },
        infrastructure: { total: 1, up: 1 },
      },
      categories: {
        ...sampleSnapshot.categories,
        services: { items: [{ name: 'DNS', ip: '1.1.1.1', overall_status: 'up', status: 'up' }] },
      },
    })

    await waitFor(() => {
      expect(screen.getAllByText((_, node) => {
        const text = node?.textContent?.replace(/\s+/g, ' ').trim() || ''
        return text.includes('3/3') && text.includes('systems operational')
      }).length).toBeGreaterThan(0)
    })
  })
})
