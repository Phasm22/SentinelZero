import React from 'react'
import { Activity, Clock, Wifi, Globe, Server } from 'lucide-react'
import HealthIndicator from './HealthIndicator'
import AnimatedValue from '../AnimatedValue'
import LabPanel from './LabPanel'

const LAYER_TABS = [
  { key: 'all', label: 'All', icon: null },
  { key: 'loopbacks', label: 'Loopbacks', icon: Wifi },
  { key: 'services', label: 'Services', icon: Globe },
  { key: 'infrastructure', label: 'Infrastructure', icon: Server },
]

const LabHealthBar = ({ healthData, filter, setFilter }) => {
  const safe = {
    total_up: 0,
    total_checks: 1,
    timestamp: null,
    layers: {
      loopbacks: { up: 0, total: 0 },
      services: { up: 0, total: 0 },
      infrastructure: { up: 0, total: 0 },
    },
    ...healthData,
  }

  const totalUp = Number.isFinite(safe.total_up) ? safe.total_up : 0
  const totalChecks = safe.total_checks > 0 ? safe.total_checks : 1

  const overallStatus = totalUp === totalChecks
    ? 'healthy'
    : totalUp > totalChecks * 0.8
      ? 'warning'
      : 'critical'

  const getTimeAgo = (timestamp) => {
    if (!timestamp) return 'updating...'
    try {
      const diffMins = Math.floor((Date.now() - new Date(timestamp)) / 60000)
      if (diffMins < 1) return 'just now'
      if (diffMins < 60) return `${diffMins}m ago`
      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}h ago`
      return `${Math.floor(diffHours / 24)}d ago`
    } catch {
      return 'unknown'
    }
  }

  return (
    <LabPanel>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <Activity className="w-6 h-6 text-blue-600 dark:text-blue-400 shrink-0" />
          <HealthIndicator status={overallStatus} variant="pill" size="md" showText />
          <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            <AnimatedValue value={totalUp} />
            <span className="text-gray-600 dark:text-gray-300">/{totalChecks}</span>
            <span className="ml-2 text-sm font-normal text-gray-600 dark:text-gray-300">operational</span>
          </span>
          <span className="text-sm font-bold text-green-600 dark:text-green-400">
            <AnimatedValue value={Math.round((totalUp / totalChecks) * 100)} suffix="%" />
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          <Clock className="w-4 h-4 shrink-0" />
          <span>Updated {getTimeAgo(safe.timestamp)}</span>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {LAYER_TABS.map(({ key, label, icon: Icon }) => {
          const isActive = filter === key
          const layer = key !== 'all' ? safe.layers?.[key] : null
          const countLabel = layer ? ` ${layer.up}/${layer.total}` : ''
          return (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white dark:bg-blue-500/30 dark:text-blue-100 border border-blue-600 dark:border-blue-400/50'
                  : 'bg-gray-100 text-gray-700 border border-gray-200 hover:bg-gray-200 dark:bg-gray-800/60 dark:text-gray-300 dark:border-gray-600/50 dark:hover:bg-gray-700/60'
              }`}
            >
              {Icon && <Icon className="w-3.5 h-3.5" />}
              {label}
              {countLabel && <span className="font-mono text-xs opacity-90">{countLabel}</span>}
            </button>
          )
        })}
      </div>
    </LabPanel>
  )
}

export default LabHealthBar
