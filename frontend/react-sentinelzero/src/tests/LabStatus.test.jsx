import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LabStatus from '../pages/LabStatus'
import { SocketProvider } from '../contexts/SocketContext'
import { apiService } from '../utils/api'

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

vi.mock('../utils/api', () => ({
  apiService: {
    getLabStatusOverview: vi.fn(),
  },
}))

vi.mock('../components/AnimatedValue', () => ({
  default: ({ value, suffix = '' }) => <span>{value}{suffix}</span>,
}))

const sampleOverview = {
  summary: {
    overall_status: 'degraded',
    health_score: 73,
    generated_at: '2026-03-08T00:00:00Z',
    window_minutes: 120,
    source_freshness: {
      opnsense: { status: 'available', age_seconds: 30 },
      whatsup: { status: 'available', age_seconds: null },
    },
  },
  attention: [
    {
      source: 'sensor',
      severity: 'high',
      title: 'yang sensor is stale',
      message: 'Last telemetry is outside the active window',
    },
  ],
  reachability: {
    overall_status: 'degraded',
    health_percentage: 66.7,
    categories: {
      loopbacks: { items: [{ name: 'Localhost', ip: '127.0.0.1', status: 'up' }] },
      services: { items: [{ name: 'DNS', ip: '1.1.1.1', overall_status: 'down', status: 'down' }] },
      infrastructure: { items: [{ name: 'Gateway', ip: '172.16.0.1', status: 'up' }] },
    },
  },
  sensor_fleet: {
    count: 2,
    active: 1,
    stale: 1,
    offline: 0,
    collector_coverage: { system: 2, proxmox: 1 },
    agents: [
      {
        agent_id: 'yang',
        hostname: 'yang.prox',
        host_ip: '172.16.0.12',
        role: 'proxmox-node',
        status: 'stale',
        latest_collectors: { system: true, proxmox: true },
      },
      {
        agent_id: 'opnsense',
        hostname: 'opnsense',
        host_ip: '172.16.0.1',
        role: 'network-sensor',
        status: 'active',
        latest_collectors: { system: true },
      },
    ],
  },
  network: {
    inventory: {
      dhcp_lease_count: 12,
      arp_entry_count: 18,
      active_arp_count: 14,
    },
    opnsense: {
      status: 'available',
      gateway_down_count: 0,
      ids: { alert_count: 1 },
    },
  },
  dns: {
    lab: {
      summary: { total_queries: 100, blocked_queries: 20, percent_blocked: 20 },
      top_blocked: [{ name: 'ads.test', count: 5 }],
    },
    home: {
      summary: { total_queries: 80, blocked_queries: 8, percent_blocked: 10 },
      top_blocked: [],
    },
  },
  flows: {
    active_host_count: 6,
    flagged_hosts: [{ ip: '172.16.0.50', score: 88 }],
  },
  infrastructure: {
    proxmox: {
      node_count: 2,
      guest_count: 8,
      running_guests: 6,
      nodes: [{ node: 'YANG', status: 'online', guest_count: 5, running_guests: 4 }],
    },
  },
  metadata: {
    missing_sources: [],
    parser_warnings: [],
  },
}

const renderLabStatus = () => render(
  <SocketProvider>
    <LabStatus />
  </SocketProvider>
)

describe('LabStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    for (const key of Object.keys(socketHandlers)) delete socketHandlers[key]
    apiService.getLabStatusOverview.mockResolvedValue(sampleOverview)
  })

  it('renders the aggregate lab status overview from the API', async () => {
    renderLabStatus()

    await waitFor(() => {
      expect(apiService.getLabStatusOverview).toHaveBeenCalledWith(120)
    })

    expect(await screen.findByText('Network Core')).toBeInTheDocument()
    expect(screen.getByText('Sensor Fleet')).toBeInTheDocument()
    expect(screen.getByText('DNS Protection')).toBeInTheDocument()
    expect(screen.getAllByText('Infrastructure').length).toBeGreaterThan(0)
    expect(screen.getByText('yang sensor is stale')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getAllByText(/operational/i).length).toBeGreaterThan(0)
  })

  it('refetches the aggregate overview when a whatsup socket update arrives', async () => {
    renderLabStatus()

    await waitFor(() => {
      expect(socketHandlers.connect).toBeTypeOf('function')
    })
    socketHandlers.connect()

    await waitFor(() => {
      expect(socketHandlers['whats_up.snapshot']).toBeTypeOf('function')
    })

    socketHandlers['whats_up.snapshot']({})

    await waitFor(() => {
      expect(apiService.getLabStatusOverview).toHaveBeenCalledTimes(2)
    })
  })

  it('shows an error state and retries when the aggregate endpoint fails', async () => {
    const user = userEvent.setup()
    apiService.getLabStatusOverview
      .mockRejectedValueOnce(new Error('route unavailable'))
      .mockResolvedValueOnce(sampleOverview)

    renderLabStatus()

    expect(await screen.findByText('Lab status unavailable')).toBeInTheDocument()
    expect(screen.getByText('route unavailable')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /retry/i }))

    expect(await screen.findByText('Network Core')).toBeInTheDocument()
    expect(apiService.getLabStatusOverview).toHaveBeenCalledTimes(2)
  })
})
