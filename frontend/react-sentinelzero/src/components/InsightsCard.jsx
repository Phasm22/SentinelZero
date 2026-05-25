import React, { useState, useEffect, useCallback } from 'react'
import { PlusCircle, AlertTriangle, CheckCircle, Clock, Filter, X } from 'lucide-react'
import { apiService } from '../utils/api'
import { useToast } from '../contexts/ToastContext'
import { useSocket } from '../contexts/SocketContext'

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

const InsightsCard = () => {
  const [insights, setInsights]     = useState([])
  const [summary, setSummary]       = useState({})
  const [isLoading, setIsLoading]   = useState(true)
  const [filter, setFilter]         = useState({ type: 'all', priority: 'all', verdict: 'all' })
  const [showFilters, setShowFilters] = useState(false)
  const [expandedId, setExpandedId] = useState(null)
  const [verdictsTick, setVerdictsTick] = useState(0)

  const { showToast }  = useToast()
  const { socket }     = useSocket()

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
    'scan_performance':  <Clock className="w-5 h-5 text-gray-400" />,
  }

  const loadInsights = useCallback(async () => {
    try {
      setIsLoading(true)

      const params = { limit: 10 }
      if (filter.type !== 'all') params.type = filter.type
      if (filter.priority === 'high') params.priority_min = 80
      if (filter.priority === 'unread') params.unread_only = true
      if (filter.verdict !== 'all') params.verdict = filter.verdict

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

  // Socket: refresh when agent posts verdicts
  useEffect(() => {
    if (!socket) return
    const handler = () => setVerdictsTick(t => t + 1)
    socket.on('insights.verdicts_ready', handler)
    return () => socket.off('insights.verdicts_ready', handler)
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

  const getPriorityColor = (priority) => {
    const thresholds = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
    const threshold  = thresholds.find(t => priority >= t) || 10
    return priorityColors[threshold] || priorityColors[10]
  }

  const toggleExpand = (id) => setExpandedId(prev => prev === id ? null : id)

  if (isLoading) {
    return (
      <div className="bg-gradient-to-br from-green-900/80 to-gray-900/60 border border-green-400/30 rounded-md shadow-xl p-6 mb-8" data-testid="insights-card">
        <h2 className="text-2xl font-title font-bold text-green-200 mb-4 flex items-center gap-2">
          <PlusCircle className="w-6 h-6 text-green-400" /> Recent Insights
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
    <div className="bg-gradient-to-br from-green-900/80 to-gray-900/60 border border-green-400/30 rounded-md shadow-xl p-3 sm:p-4 lg:p-6 mb-4 sm:mb-6 lg:mb-8" data-testid="insights-card">
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <h2 className="text-lg sm:text-xl lg:text-2xl font-title font-bold text-green-200 flex items-center gap-2">
          <PlusCircle className="w-4 h-4 sm:w-5 sm:h-5 lg:w-6 lg:h-6 text-green-400" /> Recent Insights
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
          className="text-gray-400 hover:text-white transition-colors"
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
                <option value="all">All Verdicts</option>
                <option value="escalate">Escalated</option>
                <option value="explain">Explained</option>
                <option value="dismiss">Dismissed</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {insights.length === 0 ? (
        <div className="text-center py-6 sm:py-8 text-gray-400" data-testid="no-insights">
          <PlusCircle className="w-8 h-8 sm:w-10 sm:h-10 lg:w-12 lg:h-12 mx-auto mb-2 sm:mb-3 opacity-50" data-testid="no-insights-icon" />
          <p className="text-sm sm:text-base" data-testid="no-insights-text">No insights available yet</p>
          <p className="text-xs sm:text-sm" data-testid="no-insights-hint">Complete a scan to generate insights</p>
        </div>
      ) : (
        <ul className="space-y-2 sm:space-y-3" data-testid="insights-list">
          {insights.map((insight, idx) => (
            <li
              key={insight.id || idx}
              className={`p-2 sm:p-3 rounded-md border ${getPriorityColor(insight.priority)} ${!insight.is_read ? 'ring-1 ring-current' : ''} cursor-pointer`}
              onClick={() => toggleExpand(insight.id)}
              data-testid={`insight-row-${idx}`}
            >
              <div className="flex items-start gap-2 sm:gap-3">
                <div className="flex-shrink-0 mt-0.5" data-testid="insight-icon">
                  {typeIcons[insight.type] || <PlusCircle className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400" />}
                </div>

                <div className="flex-1 min-w-0" data-testid="insight-content">
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="text-white font-medium leading-tight text-sm sm:text-base" data-testid="insight-message">{insight.message}</p>
                      <div className="flex flex-wrap items-center gap-1 sm:gap-2 mt-1" data-testid="insight-meta">
                        <span className="text-xs text-gray-400 truncate" data-testid="insight-host-time">
                          {insight.host} • {formatTime(insight.timestamp)}
                        </span>
                        {insight.scan_type && (
                          <span className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded flex-shrink-0" data-testid="insight-scan-type">
                            {insight.scan_type}
                          </span>
                        )}
                        {insight.verdict && (
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${VERDICT_STYLES[insight.verdict] || ''}`}
                            data-testid={`verdict-badge-${insight.verdict}`}
                          >
                            {insight.verdict}
                          </span>
                        )}
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
                  </div>
                </div>
              </div>

              {expandedId === insight.id && (
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
                  {!insight.verdict && !insight.verdict_summary && (
                    <p className="text-xs text-gray-500 italic mt-2">Verdict pending — agent is still running...</p>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {summary.total > insights.length && (
        <div className="mt-4 text-center" data-testid="insights-summary">
          <p className="text-sm text-gray-400" data-testid="insights-count">
            Showing {insights.length} of {summary.total} insights
          </p>
        </div>
      )}
    </div>
  )
}

export default InsightsCard
