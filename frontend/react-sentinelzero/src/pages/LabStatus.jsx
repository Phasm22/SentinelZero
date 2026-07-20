import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { useSocket } from '../contexts/SocketContext'
import { apiService } from '../utils/api'
import LabHealthBar from '../components/lab-status/LabHealthBar'
import LabOverview from '../components/lab-status/LabOverview'
import HostGrid from '../components/lab-status/HostGrid'
import LabPanel from '../components/lab-status/LabPanel'
import AttentionList from '../components/lab-status/AttentionList'
import SensorFleetPanel from '../components/lab-status/SensorFleetPanel'
import NetworkSummaryPanel from '../components/lab-status/NetworkSummaryPanel'
import DnsSummaryPanel from '../components/lab-status/DnsSummaryPanel'
import InfrastructurePanel from '../components/lab-status/InfrastructurePanel'

const initialHealthData = {
  total_checks: 0,
  total_up: 0,
  overall_status: 'unknown',
  health_score: 0,
  health_percentage: 0,
  timestamp: new Date().toISOString(),
  layers: {
    loopbacks: { total: 0, up: 0 },
    services: { total: 0, up: 0 },
    infrastructure: { total: 0, up: 0 },
  },
  categories: {
    loopbacks: { items: [] },
    services: { items: [] },
    infrastructure: { items: [] },
  },
}

const emptyOverview = {
  summary: {
    overall_status: 'unknown',
    health_score: 0,
    generated_at: null,
    window_minutes: 120,
    source_freshness: {},
  },
  attention: [],
  reachability: {},
  sensor_fleet: {},
  network: {},
  dns: {},
  flows: {},
  infrastructure: {},
  metadata: {
    missing_sources: [],
    parser_warnings: [],
  },
}

const countUp = (items = []) => items.filter((item) => item.status === 'up' || item.status === true).length

const normalizeReachability = (reachability = {}, summary = {}) => {
  const categories = {
    loopbacks: {
      items: reachability.loopbacks?.items || [],
    },
    services: {
      items: reachability.services?.items || [],
    },
    infrastructure: {
      items: reachability.infrastructure?.items || [],
    },
  }

  const layers = Object.fromEntries(
    Object.entries(categories).map(([key, value]) => [
      key,
      {
        total: Number.isFinite(reachability[key]?.total) ? reachability[key].total : value.items.length,
        up: Number.isFinite(reachability[key]?.up) ? reachability[key].up : countUp(value.items),
      },
    ])
  )

  const totalChecks = Object.values(layers).reduce((sum, layer) => sum + layer.total, 0)
  const totalUp = Object.values(layers).reduce((sum, layer) => sum + layer.up, 0)
  const healthScore = Number.isFinite(summary.health_score)
    ? summary.health_score
    : Number.isFinite(reachability.health_percentage)
      ? Math.round(reachability.health_percentage)
      : totalChecks
        ? Math.round((totalUp / totalChecks) * 100)
        : 0

  return {
    ...initialHealthData,
    ...reachability,
    total_checks: totalChecks,
    total_up: totalUp,
    health_score: healthScore,
    health_percentage: healthScore,
    overall_status: summary.overall_status || reachability.overall_status || 'unknown',
    timestamp: summary.generated_at || reachability.last_update || reachability.timestamp || new Date().toISOString(),
    layers,
    categories,
  }
}

const normalizeOverview = (payload = {}) => ({
  ...emptyOverview,
  ...payload,
  summary: {
    ...emptyOverview.summary,
    ...(payload.summary || {}),
  },
  metadata: {
    ...emptyOverview.metadata,
    ...(payload.metadata || {}),
  },
})

const LabStatus = () => {
  const [overview, setOverview] = useState(emptyOverview)
  const [healthData, setHealthData] = useState(initialHealthData)
  const [detailedData, setDetailedData] = useState({
    loopbacks: [],
    services: [],
    infrastructure: [],
  })
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')
  const { socket, isConnected } = useSocket()

  const applyOverview = useCallback((payload) => {
    const safeOverview = normalizeOverview(payload)
    const reachabilityHealth = normalizeReachability(safeOverview.reachability, safeOverview.summary)

    setOverview(safeOverview)
    setHealthData(reachabilityHealth)
    setDetailedData({
      loopbacks: reachabilityHealth.categories.loopbacks.items,
      services: reachabilityHealth.categories.services.items,
      infrastructure: reachabilityHealth.categories.infrastructure.items,
    })
    setError(null)
  }, [])

  const fetchOverview = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    setRefreshing(true)

    try {
      const data = await apiService.getLabStatusOverview(120)
      applyOverview(data)
    } catch (err) {
      console.error('Failed to fetch lab status overview:', err)
      setError(err?.response?.data?.error || err.message || 'Failed to fetch lab status overview')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [applyOverview])

  useEffect(() => {
    fetchOverview()
    const interval = setInterval(() => fetchOverview({ silent: true }), 30000)
    return () => clearInterval(interval)
  }, [fetchOverview])

  useEffect(() => {
    if (!socket || !isConnected) return undefined

    const handleRefreshSignal = () => {
      fetchOverview({ silent: true })
    }

    socket.on('whats_up.snapshot', handleRefreshSignal)

    return () => {
      socket.off('whats_up.snapshot', handleRefreshSignal)
    }
  }, [fetchOverview, socket, isConnected])

  const freshnessItems = useMemo(() => (
    Object.entries(overview.summary.source_freshness || {}).filter(([, value]) => value)
  ), [overview.summary.source_freshness])

  const warnings = overview.metadata.parser_warnings || []
  const missingSources = overview.metadata.missing_sources || []

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 sm:space-y-5 sm:p-6">
      {loading && (
        <LabPanel>
          <div className="flex items-center justify-center space-x-3">
            <div className="h-6 w-6 animate-spin rounded-full border-b-2 border-blue-400" />
            <span className="text-gray-300">Loading lab status...</span>
          </div>
        </LabPanel>
      )}

      {error && (
        <LabPanel className="!p-4 border-red-500/30">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
              <div>
                <div className="text-sm font-semibold text-red-200">Lab status unavailable</div>
                <div className="text-sm text-gray-300">{error}</div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => fetchOverview()}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200 hover:bg-red-500/20"
            >
              <RefreshCw className="h-4 w-4" />
              Retry
            </button>
          </div>
        </LabPanel>
      )}

      <LabHealthBar healthData={healthData} filter={filter} setFilter={setFilter} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-4">
          <LabOverview healthData={healthData} detailedData={detailedData} />
          <NetworkSummaryPanel network={overview.network} flows={overview.flows} />
          <DnsSummaryPanel dns={overview.dns} />
          <InfrastructurePanel infrastructure={overview.infrastructure} reachability={overview.reachability} />
        </div>

        <div className="space-y-4">
          <AttentionList items={overview.attention} />
          <SensorFleetPanel fleet={overview.sensor_fleet} />
          {(warnings.length > 0 || missingSources.length > 0 || freshnessItems.length > 0) && (
            <LabPanel className="!p-4">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="card-heading text-base">Sources</h2>
                {refreshing && <RefreshCw className="h-4 w-4 animate-spin text-gray-500" />}
              </div>
              <div className="space-y-2">
                {freshnessItems.map(([name, data]) => (
                  <div key={name} className="flex items-center justify-between gap-3 text-xs">
                    <span className="text-gray-300">{name}</span>
                    <span className="font-mono text-gray-500">{data.status || 'unknown'}</span>
                  </div>
                ))}
                {missingSources.length > 0 && (
                  <div className="rounded-md border border-yellow-500/20 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200">
                    Missing: {missingSources.join(', ')}
                  </div>
                )}
                {warnings.slice(0, 3).map((warning, index) => (
                  <div key={`${warning}-${index}`} className="rounded-md border border-orange-500/20 bg-orange-500/10 px-3 py-2 text-xs text-orange-200">
                    {warning}
                  </div>
                ))}
              </div>
            </LabPanel>
          )}
        </div>
      </div>

      <HostGrid detailedData={detailedData} filter={filter} />
    </div>
  )
}

export default LabStatus
