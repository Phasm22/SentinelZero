import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { PlusCircle, AlertTriangle, CheckCircle, Clock, Filter, X, Sparkles, ChevronDown, ChevronRight } from 'lucide-react'
import { apiService } from '../utils/api'
import { useToast } from '../contexts/ToastContext'
import { useSocket } from '../contexts/SocketContext'
import InfoModalTrigger from './InfoModalTrigger'
import { InsightsCardHelp, PivotMissionButtonHelp } from './hunter/hunterHelpContent'

const VERDICT_STYLES = {
  escalate: 'bg-red-500/20 text-red-400 border border-red-500/40',
  explain:  'bg-green-500/20 text-green-400 border border-green-500/40',
  dismiss:  'bg-gray-500/20 text-gray-400 border border-gray-500/40',
}

const ContextBlock = ({ title, children }) => (
  <div className="mt-2">
    <p className="text-xs text-gray-300 font-medium mb-1">{title}</p>
    <pre className="text-xs text-gray-400 font-mono leading-relaxed whitespace-pre-wrap break-words">
      {children}
    </pre>
  </div>
)

const formatSensorContext = (ctx) => {
  if (!ctx) return null
  const lines = []
  if (ctx.endpoint) {
    const e = ctx.endpoint
    lines.push(
      `Process: ${e.process_name || '?'} (PID ${e.pid ?? '?'})`,
      e.minutes_before_scan != null ? `Started ~${e.minutes_before_scan} min before scan` : null,
      e.cmdline ? `Cmd: ${e.cmdline}` : null,
    )
  }
  if (ctx.network) {
    const n = ctx.network
    if (n.top_blocked?.length) {
      lines.push('DNS blocked (segment): ' + n.top_blocked.map(b => b.domain || b[0]).join(', '))
    }
    if (n.alerted_flows?.length) {
      lines.push(`ntopng alerts: ${n.alerted_flows.length} engaged`)
    }
    if (n.ids_alerts?.length) {
      lines.push(`OPNsense IDS: ${n.ids_alerts.length} hits for host`)
    }
  }
  return lines.filter(Boolean).join('\n') || null
}

const VERDICT_STATUS_STYLES = {
  pending: 'text-gray-400',
  skipped: 'text-yellow-400',
  failed: 'text-red-400',
  timeout: 'text-red-400',
  success: 'text-orange-300',
  auto: 'text-gray-500',
}

const formatVerdictPending = (insight) => {
  if (insight.verdict || insight.verdict_summary) return null
  const note = insight.verdict_status_note
  if (!note) return { text: 'No verdict yet', className: 'text-gray-500' }
  const status = insight.verdict_agent_status || 'pending'
  return {
    text: note,
    className: VERDICT_STATUS_STYLES[status] || 'text-gray-500',
  }
}

const PIVOT_ELIGIBLE_TYPES = new Set([
  'new_host', 'new_port', 'service_change', 'new_vuln_critical', 'new_vuln_high',
  'registry_gap', 'inventory_gap', 'sensor_gap', 'correlated',
])

const isPivotEligible = (insight) => {
  if (insight.verdict !== 'escalate') return false
  const label = insight.network_label || insight.details?.network_label
  if (label !== 'Lab') return false
  const host = insight.host || insight.details?.ip
  if (!host || !/^\d+\.\d+\.\d+\.\d+$/.test(host)) return false
  return PIVOT_ELIGIBLE_TYPES.has(insight.type)
}

const getPivotIneligibleHint = (insight) => {
  if (insight.verdict !== 'escalate' || isPivotEligible(insight)) return null

  const label = insight.network_label || insight.details?.network_label
  if (label && label !== 'Lab') {
    return 'Escalated, but pivot missions are Lab-only (Home insights excluded).'
  }

  const host = insight.host || insight.details?.ip
  if (host && !/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
    return 'Escalated rollup insight — pivot requires a single host IP (e.g. new port on one machine).'
  }

  if (!PIVOT_ELIGIBLE_TYPES.has(insight.type)) {
    return `Escalated, but ${insight.type.replace(/_/g, ' ')} is not a pivot-eligible finding type.`
  }

  return 'Escalated, but does not meet pivot criteria (Lab + single IP + eligible type).'
}

const BLOCKING_MISSION_STATES = new Set(['running', 'queued', 'done'])

const getPivotMissionState = (insight, missionsByInsightId) => {
  const mission = missionsByInsightId.get(insight.id)
  if (!mission) return null
  const state = mission.state || 'unknown'
  if (!BLOCKING_MISSION_STATES.has(state)) return null
  return state
}

const getPivotButtonLabel = (state, isSpawning) => {
  if (isSpawning) return 'Starting pivot…'
  if (state === 'running' || state === 'queued') return 'Pivot running…'
  if (state === 'done') return 'Pivot completed'
  return 'Start pivot mission'
}

const InsightsCard = () => {
  const [insights, setInsights]     = useState([])
  const [summary, setSummary]       = useState({})
  const [isLoading, setIsLoading]   = useState(true)
  const [filter, setFilter]         = useState({ type: 'all', priority: 'all', verdict: 'actionable' })
  const [showFilters, setShowFilters] = useState(false)
  const [expandedId, setExpandedId] = useState(null)
  const [verdictsTick, setVerdictsTick] = useState(0)
  const [spawningPivotId, setSpawningPivotId] = useState(null)
  const [pivotMissions, setPivotMissions] = useState([])

  const { showToast }  = useToast()
  const { socket }     = useSocket()

  const missionsByInsightId = useMemo(() => {
    const map = new Map()
    for (const mission of pivotMissions) {
      if (!mission?.insightId) continue
      const existing = map.get(mission.insightId)
      if (!existing) {
        map.set(mission.insightId, mission)
        continue
      }
      const existingTs = Date.parse(existing.updatedAt || existing.startedAt || 0) || 0
      const missionTs = Date.parse(mission.updatedAt || mission.startedAt || 0) || 0
      if (missionTs >= existingTs) {
        map.set(mission.insightId, mission)
      }
    }
    return map
  }, [pivotMissions])

  const loadPivotMissions = useCallback(async () => {
    try {
      const payload = await apiService.getHunterMissions(50)
      setPivotMissions(payload?.missions || [])
    } catch (error) {
      console.error('Error loading pivot missions:', error)
    }
  }, [])

  const priorityColors = {
    100: 'text-red-400 bg-red-900/30 border-red-400/30',
    90:  'text-red-400 bg-red-900/30 border-red-400/30',
    80:  'text-orange-400 bg-orange-900/30 border-orange-400/30',
    70:  'text-yellow-400 bg-yellow-900/30 border-yellow-400/30',
    60:  'text-blue-400 bg-blue-900/30 border-blue-400/30',
    50:  'text-green-400 bg-green-900/30 border-green-400/30',
    40:  'text-cyan-400 bg-cyan-900/30 border-cyan-400/30',
    30:  'text-gray-400 bg-gray-900/30 border-gray-400/30',
    20:  'text-gray-400 bg-gray-900/30 border-gray-400/30',
    10:  'text-gray-400 bg-gray-900/30 border-gray-400/30',
  }

  const typeIcons = {
    'new_vuln_critical': <AlertTriangle className="w-5 h-5 text-red-400" />,
    'new_vuln_high':     <AlertTriangle className="w-5 h-5 text-red-400" />,
    'new_vuln_medium':   <AlertTriangle className="w-5 h-5 text-yellow-400" />,
    'new_vuln_low':      <AlertTriangle className="w-5 h-5 text-gray-400" />,
    'new_host':          <PlusCircle className="w-5 h-5 text-blue-400" />,
    'missing_host':      <X className="w-5 h-5 text-orange-400" />,
    'new_port':          <PlusCircle className="w-5 h-5 text-green-400" />,
    'port_closed':       <X className="w-5 h-5 text-gray-400" />,
    'service_change':    <Clock className="w-5 h-5 text-cyan-400" />,
    'vuln_resolved':     <CheckCircle className="w-5 h-5 text-green-400" />,
    'registry_gap':      <AlertTriangle className="w-5 h-5 text-amber-400" />,
    'sensor_gap':        <AlertTriangle className="w-5 h-5 text-amber-400" />,
    'baseline_inventory': <Clock className="w-5 h-5 text-gray-400" />,
    'correlated':        <AlertTriangle className="w-5 h-5 text-violet-400" />,
    'scan_performance':  <Clock className="w-5 h-5 text-gray-400" />,
  }

  const loadInsights = useCallback(async () => {
    try {
      setIsLoading(true)

      const params = { limit: 10 }
      if (filter.type !== 'all') params.type = filter.type
      if (filter.priority === 'high') params.priority_min = 80
      if (filter.priority === 'unread') params.unread_only = true
      if (filter.verdict && filter.verdict !== 'all') params.verdict = filter.verdict

      const data = await apiService.getInsights(params)
      setInsights(data.insights || [])
      setSummary(data.summary || {})
    } catch (error) {
      console.error('Error loading insights:', error)
      showToast('Failed to load insights', 'danger')
      setInsights([])
      setSummary({})
    } finally {
      setIsLoading(false)
    }
  }, [filter, showToast])

  // Reload when filter changes or verdicts land
  useEffect(() => {
    loadInsights()
  }, [loadInsights, verdictsTick])

  useEffect(() => {
    loadPivotMissions()
  }, [loadPivotMissions])

  // Socket: refresh when agent posts verdicts
  useEffect(() => {
    if (!socket) return
    const handler = () => setVerdictsTick(t => t + 1)
    socket.on('insights.verdicts_ready', handler)
    socket.on('insights.synthesis_ready', handler)
    return () => {
      socket.off('insights.verdicts_ready', handler)
      socket.off('insights.synthesis_ready', handler)
    }
  }, [socket])

  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    try { return new Date(timestamp).toLocaleString() } catch { return '' }
  }

  const handleMarkAsRead = async (e, insightId) => {
    e.stopPropagation()
    try {
      await apiService.markInsightsRead([insightId])
      setInsights(prev => prev.map(i => i.id === insightId ? { ...i, is_read: true } : i))
      showToast('Insight marked as read', 'success')
    } catch (error) {
      console.error('Error marking insight as read:', error)
      showToast('Failed to mark insight as read', 'danger')
    }
  }

  const handleSpawnPivot = async (e, insight) => {
    e.stopPropagation()
    const existingState = getPivotMissionState(insight, missionsByInsightId)
    if (existingState) {
      const mission = missionsByInsightId.get(insight.id)
      showToast(
        `Pivot mission already ${existingState}${mission?.missionId ? `: ${mission.missionId}` : ''}`,
        'warning'
      )
      return
    }
    setSpawningPivotId(insight.id)
    try {
      const result = await apiService.spawnHunterMission({
        insight_id: insight.id,
        ip: insight.host,
        type: insight.type,
        scan_id: insight.scan_id,
        network_label: insight.network_label || insight.details?.network_label || 'Lab',
        target_network: insight.details?.target_network || '172.16.0.0/22',
        iface: 'enp6s18',
      })
      showToast(`Pivot mission started: ${result.mission_id}`, 'success')
      await loadPivotMissions()
    } catch (error) {
      const status = error?.response?.status
      const data = error?.response?.data || {}
      if (status === 409 && data.status === 'duplicate') {
        showToast(data.reason || `Pivot mission already ${data.state || 'active'}`, 'warning')
        await loadPivotMissions()
      } else {
        const msg = data.reason || data.error || 'Failed to start pivot mission'
        showToast(msg, 'danger')
      }
    } finally {
      setSpawningPivotId(null)
    }
  }

  const getPriorityColor = (priority) => {
    const thresholds = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
    const threshold  = thresholds.find(t => priority >= t) || 10
    return priorityColors[threshold] || priorityColors[10]
  }

  const toggleExpand = (id) => setExpandedId(prev => prev === id ? null : id)

  if (isLoading) {
    return (
      <div className="card-glass p-6 mb-8" data-testid="insights-card">
        <h2 className="text-2xl card-title mb-4 flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-green-400" /> Recent Insights
        </h2>
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-white/5 rounded-md"></div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="card-glass p-3 sm:p-4 lg:p-6 mb-4 sm:mb-6 lg:mb-8" data-testid="insights-card">
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <h2 className="text-lg sm:text-xl lg:text-2xl card-title flex items-center gap-2">
          <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 lg:w-6 lg:h-6 text-green-400" />
          Recent Insights
          <InfoModalTrigger
            title="Recent Insights & Pivot Missions"
            ariaLabel="How insights and pivot missions work"
            testId="insights-card-help"
            iconClassName="w-4 h-4 sm:w-5 sm:h-5"
          >
            <InsightsCardHelp />
          </InfoModalTrigger>
          {summary.escalated > 0 && (
            <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
              {summary.escalated} escalated
            </span>
          )}
          {summary.unread > 0 && (
            <span className="bg-orange-500 text-white text-xs px-1.5 py-0.5 rounded-full">
              {summary.unread}
            </span>
          )}
        </h2>

        <button
          onClick={() => setShowFilters(!showFilters)}
          className="text-gray-400 hover:text-gray-200 transition-colors"
          data-testid="filter-toggle-btn"
        >
          <Filter className="w-5 h-5" />
        </button>
      </div>

      {showFilters && (
        <div className="mb-3 sm:mb-4 p-2 sm:p-3 bg-black/20 rounded-md border border-gray-600/30" data-testid="filter-panel">
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 lg:gap-4">
            <div className="flex-1">
              <label className="text-xs sm:text-sm text-gray-300 block mb-1" data-testid="type-filter-label">Type</label>
              <select
                value={filter.type}
                onChange={(e) => setFilter(prev => ({ ...prev, type: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs sm:text-sm text-white"
                data-testid="type-filter-select"
              >
                <option value="all">All Types</option>
                <option value="new_vuln_critical">Critical Vulns</option>
                <option value="new_vuln_high">High Vulns</option>
                <option value="new_host">New Hosts</option>
                <option value="missing_host">Missing Hosts</option>
                <option value="new_port">New Ports</option>
              </select>
            </div>

            <div className="flex-1">
              <label className="text-xs sm:text-sm text-gray-300 block mb-1" data-testid="priority-filter-label">Priority</label>
              <select
                value={filter.priority}
                onChange={(e) => setFilter(prev => ({ ...prev, priority: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs sm:text-sm text-white"
                data-testid="priority-filter-select"
              >
                <option value="all">All Priorities</option>
                <option value="high">High Priority (80+)</option>
                <option value="unread">Unread Only</option>
              </select>
            </div>

            <div className="flex-1">
              <label className="text-xs sm:text-sm text-gray-300 block mb-1">Verdict</label>
              <select
                value={filter.verdict}
                onChange={(e) => setFilter(prev => ({ ...prev, verdict: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs sm:text-sm text-white"
                data-testid="verdict-filter-select"
              >
                <option value="actionable">Escalate & Explain</option>
                <option value="escalate">Escalated only</option>
                <option value="explain">Explained only</option>
                <option value="dismiss">Dismissed</option>
                <option value="all">All verdicts</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {insights.length === 0 ? (
        <div className="text-center py-6 sm:py-8 card-meta" data-testid="no-insights">
          <PlusCircle className="w-8 h-8 sm:w-10 sm:h-10 lg:w-12 lg:h-12 mx-auto mb-2 sm:mb-3 opacity-50" data-testid="no-insights-icon" />
          <p className="text-sm sm:text-base" data-testid="no-insights-text">No insights available yet</p>
          <p className="text-xs sm:text-sm" data-testid="no-insights-hint">Complete a scan to generate insights</p>
        </div>
      ) : (
        <ul className="space-y-2 sm:space-y-3" data-testid="insights-list">
          {insights.map((insight, idx) => {
            const isExpanded = expandedId === insight.id
            return (
            <li
              key={insight.id || idx}
              role="button"
              tabIndex={0}
              aria-expanded={isExpanded}
              className={`p-2 sm:p-3 rounded-md border transition-colors ${getPriorityColor(insight.priority)} ${!insight.is_read ? 'ring-1 ring-current' : ''} cursor-pointer hover:bg-white/5 ${isExpanded ? 'bg-white/5' : ''}`}
              onClick={() => toggleExpand(insight.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  toggleExpand(insight.id)
                }
              }}
              data-testid={`insight-row-${idx}`}
            >
              <div className="flex items-start gap-2 sm:gap-3">
                <div className="flex-shrink-0 mt-0.5" data-testid="insight-icon">
                  {typeIcons[insight.type] || <PlusCircle className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400" />}
                </div>

                <div className="flex-1 min-w-0" data-testid="insight-content">
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="text-gray-100 font-medium leading-tight text-sm sm:text-base" data-testid="insight-message">{insight.message}</p>
                      <div className="flex flex-wrap items-center gap-1 sm:gap-2 mt-1" data-testid="insight-meta">
                        <span className="text-xs text-gray-400 truncate" data-testid="insight-host-time">
                          {insight.host} • {formatTime(insight.timestamp)}
                        </span>
                        {insight.network_label && (
                          <span className="text-xs px-1.5 py-0.5 rounded flex-shrink-0 bg-indigo-900/40 text-indigo-200 border border-indigo-500/30">
                            {insight.network_label}
                          </span>
                        )}
                        {insight.scan_type && (
                          <span className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded flex-shrink-0" data-testid="insight-scan-type">
                            {insight.scan_type}
                          </span>
                        )}
                        {insight.verdict ? (
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${VERDICT_STYLES[insight.verdict] || ''}`}
                            data-testid={`verdict-badge-${insight.verdict}`}
                          >
                            {insight.verdict}
                          </span>
                        ) : insight.verdict_agent_status && insight.verdict_agent_status !== 'complete' ? (
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 border border-dashed ${
                              insight.verdict_agent_status === 'skipped' ? 'text-yellow-400 border-yellow-500/40' :
                              insight.verdict_agent_status === 'pending' ? 'text-gray-400 border-gray-500/40' :
                              'text-orange-300 border-orange-500/40'
                            }`}
                            data-testid={`verdict-status-${insight.verdict_agent_status}`}
                            title={insight.verdict_status_note || ''}
                          >
                            {insight.verdict_agent_status}
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {!insight.is_read && (
                      <button
                        onClick={(e) => handleMarkAsRead(e, insight.id)}
                        className="text-xs text-gray-400 hover:text-white transition-colors ml-2 flex-shrink-0"
                        data-testid={`mark-read-btn-${insight.id}`}
                      >
                        <CheckCircle className="w-3 h-3 sm:w-4 sm:h-4" />
                      </button>
                    )}
                    <div className="flex items-center gap-1 ml-2 flex-shrink-0 card-meta">
                      <span className="hidden sm:inline text-xs">Details</span>
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4" aria-hidden="true" />
                      ) : (
                        <ChevronRight className="w-4 h-4" aria-hidden="true" />
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {isExpanded && (
                <div className="mt-2 pt-2 border-t border-white/10 ml-7 sm:ml-8" data-testid="insight-expanded">
                  {insight.details?.asset_context && (
                    <ContextBlock title="Asset">
                      {`${insight.details.asset_context.name || insight.host} · ${insight.details.asset_context.role || 'unknown'} · zone ${insight.details.asset_context.trust_zone || '?'}`}
                      {insight.details.unexpected_port ? '\n⚠ Port not in expected_ports' : ''}
                    </ContextBlock>
                  )}
                  {formatSensorContext(insight.details?.sensor_context) && (
                    <ContextBlock title="Sensor context">
                      {formatSensorContext(insight.details.sensor_context)}
                    </ContextBlock>
                  )}
                  {insight.verdict_summary && (
                    <p className="text-xs text-gray-200 mt-2 font-medium">{insight.verdict_summary}</p>
                  )}
                  {insight.verdict_evidence && (
                    <p className="text-xs text-gray-400 font-mono leading-relaxed mt-1">{insight.verdict_evidence}</p>
                  )}
                  {isPivotEligible(insight) && (() => {
                    const pivotState = getPivotMissionState(insight, missionsByInsightId)
                    const isSpawning = spawningPivotId === insight.id
                    const isBlocked = Boolean(pivotState) || isSpawning
                    return (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={(e) => handleSpawnPivot(e, insight)}
                        disabled={isBlocked}
                        className="text-xs px-3 py-1.5 rounded border border-purple-500/40 bg-purple-900/30 text-purple-200 hover:bg-purple-900/50 disabled:opacity-50"
                        data-testid={`spawn-pivot-${insight.id}`}
                      >
                        {getPivotButtonLabel(pivotState, isSpawning)}
                      </button>
                      <InfoModalTrigger
                        title="Start Pivot Mission"
                        ariaLabel="What a pivot mission does"
                        testId={`spawn-pivot-help-${insight.id}`}
                        iconClassName="w-3.5 h-3.5"
                      >
                        <PivotMissionButtonHelp />
                      </InfoModalTrigger>
                    </div>
                    )
                  })()}
                  {(() => {
                    const pivotHint = getPivotIneligibleHint(insight)
                    if (!pivotHint) return null
                    return (
                      <p
                        className="text-xs text-amber-300/90 mt-3 leading-relaxed"
                        data-testid={`pivot-ineligible-hint-${insight.id}`}
                      >
                        {pivotHint}
                      </p>
                    )
                  })()}
                  {(() => {
                    const pending = formatVerdictPending(insight)
                    if (!pending) return null
                    return (
                      <p className={`text-xs italic mt-2 ${pending.className}`} data-testid="verdict-status-note">
                        {pending.text}
                        {insight.scan_id && insight.verdict_agent_status === 'skipped' && (
                          <span className="block text-gray-500 mt-1 not-italic">
                            Scan #{insight.scan_id} → View details → AI tab
                          </span>
                        )}
                      </p>
                    )
                  })()}
                </div>
              )}
            </li>
          )})}
        </ul>
      )}

      {summary.total > insights.length && (
        <div className="mt-4 text-center" data-testid="insights-summary">
          <p className="card-meta" data-testid="insights-count">
            Showing {insights.length} of {summary.total} insights
          </p>
        </div>
      )}
    </div>
  )
}

export default InsightsCard
