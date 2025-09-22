import React, { useState, useEffect } from 'react'
import { PlusCircle, AlertTriangle, CheckCircle, Clock, Filter, X } from 'lucide-react'
import { apiService } from '../utils/api'
import { useToast } from '../contexts/ToastContext'

const InsightsCard = () => {
  const [insights, setInsights] = useState([])
  const [summary, setSummary] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState({ type: 'all', priority: 'all' })
  const [showFilters, setShowFilters] = useState(false)
  const { showToast } = useToast()

  // Priority and type mappings for UI
  const priorityColors = {
    100: 'text-red-400 bg-red-900/30 border-red-400/30', // Critical
    90: 'text-red-400 bg-red-900/30 border-red-400/30',  // High
    80: 'text-orange-400 bg-orange-900/30 border-orange-400/30', // Missing host
    70: 'text-yellow-400 bg-yellow-900/30 border-yellow-400/30', // Medium
    60: 'text-blue-400 bg-blue-900/30 border-blue-400/30', // New host
    50: 'text-green-400 bg-green-900/30 border-green-400/30', // New port
    40: 'text-cyan-400 bg-cyan-900/30 border-cyan-400/30', // Service change
    30: 'text-gray-400 bg-gray-900/30 border-gray-400/30', // Low
    20: 'text-gray-400 bg-gray-900/30 border-gray-400/30', // Port closed
    10: 'text-gray-400 bg-gray-900/30 border-gray-400/30'  // Performance
  }

  const typeIcons = {
    'new_vuln_critical': <AlertTriangle className="w-5 h-5 text-red-400" />,
    'new_vuln_high': <AlertTriangle className="w-5 h-5 text-red-400" />,
    'new_vuln_medium': <AlertTriangle className="w-5 h-5 text-yellow-400" />,
    'new_vuln_low': <AlertTriangle className="w-5 h-5 text-gray-400" />,
    'new_host': <PlusCircle className="w-5 h-5 text-blue-400" />,
    'missing_host': <X className="w-5 h-5 text-orange-400" />,
    'new_port': <PlusCircle className="w-5 h-5 text-green-400" />,
    'port_closed': <X className="w-5 h-5 text-gray-400" />,
    'service_change': <Clock className="w-5 h-5 text-cyan-400" />,
    'scan_performance': <Clock className="w-5 h-5 text-gray-400" />
  }

  useEffect(() => {
    loadInsights()
  }, [filter])

  const loadInsights = async () => {
    try {
      setIsLoading(true)
      
      const params = { limit: 10 }
      if (filter.type !== 'all') params.type = filter.type
      if (filter.priority === 'high') params.priority_min = 80
      if (filter.priority === 'unread') params.unread_only = true
      
      const data = await apiService.getInsights(params)
      setInsights(data.insights || [])
      setSummary(data.summary || {})
      
    } catch (error) {
      console.error('Error loading insights:', error)
      showToast('Failed to load insights', 'danger')
      // Show empty state on error
      setInsights([])
      setSummary({})
    } finally {
      setIsLoading(false)
    }
  }

  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    try {
      return new Date(timestamp).toLocaleString()
    } catch {
      return ''
    }
  }

  const handleMarkAsRead = async (insightId) => {
    try {
      await apiService.markInsightsRead([insightId])
      // Update local state
      setInsights(prev => prev.map(insight => 
        insight.id === insightId ? { ...insight, is_read: true } : insight
      ))
      showToast('Insight marked as read', 'success')
    } catch (error) {
      console.error('Error marking insight as read:', error)
      showToast('Failed to mark insight as read', 'danger')
    }
  }

  const getPriorityColor = (priority) => {
    const thresholds = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
    const threshold = thresholds.find(t => priority >= t) || 10
    return priorityColors[threshold] || priorityColors[10]
  }

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
    <div className="bg-gradient-to-br from-green-900/80 to-gray-900/60 border border-green-400/30 rounded-md shadow-xl p-6 mb-8" data-testid="insights-card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-title font-bold text-green-200 flex items-center gap-2">
          <PlusCircle className="w-6 h-6 text-green-400" /> Recent Insights
          {summary.unread > 0 && (
            <span className="bg-red-500 text-white text-xs px-2 py-1 rounded-full">
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
        <div className="mb-4 p-3 bg-black/20 rounded-md border border-gray-600/30" data-testid="filter-panel">
          <div className="flex gap-4">
            <div>
              <label className="text-sm text-gray-300 block mb-1" data-testid="type-filter-label">Type</label>
              <select
                value={filter.type}
                onChange={(e) => setFilter(prev => ({ ...prev, type: e.target.value }))}
                className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white"
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
            
            <div>
              <label className="text-sm text-gray-300 block mb-1" data-testid="priority-filter-label">Priority</label>
              <select
                value={filter.priority}
                onChange={(e) => setFilter(prev => ({ ...prev, priority: e.target.value }))}
                className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white"
                data-testid="priority-filter-select"
              >
                <option value="all">All Priorities</option>
                <option value="high">High Priority (80+)</option>
                <option value="unread">Unread Only</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {insights.length === 0 ? (
        <div className="text-center py-8 text-gray-400" data-testid="no-insights">
          <PlusCircle className="w-12 h-12 mx-auto mb-3 opacity-50" data-testid="no-insights-icon" />
          <p data-testid="no-insights-text">No insights available yet</p>
          <p className="text-sm" data-testid="no-insights-hint">Complete a scan to generate insights</p>
        </div>
      ) : (
        <ul className="space-y-3" data-testid="insights-list">
          {insights.map((insight, idx) => (
            <li key={insight.id || idx} className={`flex items-center gap-3 p-3 rounded-md border ${getPriorityColor(insight.priority)} ${!insight.is_read ? 'ring-1 ring-current' : ''}`} data-testid={`insight-row-${idx}`}>
              <div className="flex-shrink-0" data-testid="insight-icon">
                {typeIcons[insight.type] || <PlusCircle className="w-5 h-5 text-gray-400" />}
              </div>
              
              <div className="flex-1 min-w-0" data-testid="insight-content">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-white font-medium leading-tight" data-testid="insight-message">{insight.message}</p>
                    <div className="flex items-center gap-2 mt-1" data-testid="insight-meta">
                      <span className="text-xs text-gray-400" data-testid="insight-host-time">
                        {insight.host} • {formatTime(insight.timestamp)}
                      </span>
                      {insight.scan_type && (
                        <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded" data-testid="insight-scan-type">
                          {insight.scan_type}
                        </span>
                      )}
                    </div>
                  </div>
                  
                  {!insight.is_read && (
                    <button
                      onClick={() => handleMarkAsRead(insight.id)}
                      className="text-xs text-gray-400 hover:text-white transition-colors ml-2 flex-shrink-0"
                      data-testid={`mark-read-btn-${insight.id}`}
                    >
                      <CheckCircle className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
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