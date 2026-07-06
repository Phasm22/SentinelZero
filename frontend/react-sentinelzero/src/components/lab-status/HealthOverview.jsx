import React from 'react'
import { Activity, Clock } from 'lucide-react'
import HealthIndicator from './HealthIndicator'
import AnimatedValue from '../AnimatedValue'

const HealthOverview = ({ healthData }) => {
  const safeHealthData = {
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

  const totalUp = Number.isFinite(safeHealthData.total_up) ? safeHealthData.total_up : 0
  const totalChecks = Number.isFinite(safeHealthData.total_checks) && safeHealthData.total_checks > 0 ? safeHealthData.total_checks : 1

  const getOverallStatus = () => {
    if (totalUp === totalChecks) return 'healthy'
    if (totalUp > totalChecks * 0.8) return 'warning'
    return 'critical'
  }

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

  const overallStatus = getOverallStatus()

  return (
    <div className="card-glass p-4 sm:p-6 transition-all duration-200 hover:shadow-2xl">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 sm:w-8 sm:h-8 text-blue-400" />
            <div>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                <HealthIndicator status={overallStatus} variant="pill" size="md" showText />
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mt-2">
                <span className="text-lg sm:text-xl text-gray-100">
                  <AnimatedValue value={totalUp} />
                  <span className="text-gray-300">/{totalChecks}</span>
                  <span className="text-gray-200 ml-2">systems operational</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="text-left lg:text-right">
          <div className="flex items-center gap-2 card-body">
            <Clock className="w-4 h-4 text-gray-400" />
            <span className="text-gray-400">
              Last updated: {getTimeAgo(safeHealthData.timestamp)}
            </span>
          </div>

          <div className="mt-2">
            <div className="text-xl sm:text-2xl font-bold text-green-400">
              <AnimatedValue value={Math.round((totalUp / totalChecks) * 100)} suffix="%" />
            </div>
            <div className="card-body">uptime</div>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between card-body mb-3">
          <span>System Health</span>
          <span className="font-mono text-gray-100">{totalUp}/{totalChecks}</span>
        </div>

        <div className="flex gap-1">
          {[...Array(totalChecks)].map((_, i) => (
            <div
              key={i}
              className={`h-2 flex-1 rounded-full transition-all duration-300 ${
                i < totalUp
                  ? 'bg-gradient-to-t from-green-500 to-green-400 shadow-sm shadow-green-400/50'
                  : 'bg-gray-700/50'
              }`}
              style={{
                animationDelay: `${i * 50}ms`,
                animation: i < totalUp ? 'pulse-glow 2s ease-in-out infinite' : 'none',
              }}
            />
          ))}
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-blue-400/80" />
            <span className="card-meta">Loopbacks</span>
            <span className="card-meta text-blue-400 font-mono">
              {safeHealthData.layers?.loopbacks?.up || 0}/{safeHealthData.layers?.loopbacks?.total || 0}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-purple-400/80" />
            <span className="card-meta">Services</span>
            <span className="card-meta text-purple-400 font-mono">
              {safeHealthData.layers?.services?.up || 0}/{safeHealthData.layers?.services?.total || 0}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-cyan-400/80" />
            <span className="card-meta">Infrastructure</span>
            <span className="card-meta text-cyan-400 font-mono">
              {safeHealthData.layers?.infrastructure?.up || 0}/{safeHealthData.layers?.infrastructure?.total || 0}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default HealthOverview
