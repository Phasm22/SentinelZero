import React from 'react'
import { Activity, Clock } from 'lucide-react'
import HealthIndicator from './HealthIndicator'
import AnimatedValue from '../AnimatedValue'

const HealthOverview = ({ healthData }) => {
  if (!healthData) return null

  const getOverallStatus = () => {
    if (healthData.total_up === healthData.total_checks) return 'healthy'
    if (healthData.total_up > healthData.total_checks * 0.8) return 'warning'
    return 'critical'
  }

  const getTimeAgo = (timestamp) => {
    if (!timestamp) return 'updating...'
    
    try {
      const now = new Date()
      const then = new Date(timestamp)
      const diffMs = now - then
      const diffMins = Math.floor(diffMs / 60000)
      
      if (diffMins < 1) return 'just now'
      if (diffMins < 60) return `${diffMins}m ago`
      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}h ago`
      const diffDays = Math.floor(diffHours / 24)
      return `${diffDays}d ago`
    } catch (error) {
      return 'unknown'
    }
  }

  const overallStatus = getOverallStatus()

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 dark:from-gray-800/80 dark:to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-4 sm:p-6 transition-all duration-200 hover:shadow-2xl">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 sm:w-8 sm:h-8 text-blue-400 dark:text-blue-400" />
            <div>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                <HealthIndicator 
                  status={overallStatus} 
                  variant="pill" 
                  size="md" 
                  showText 
                />
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mt-2">
                <span className="text-lg sm:text-xl text-gray-300 dark:text-gray-300">
                  <AnimatedValue value={healthData.total_up} />
                  <span className="text-gray-600 dark:text-gray-500">/{healthData.total_checks}</span>
                  <span className="text-gray-700 dark:text-gray-400 ml-2">systems operational</span>
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <div className="text-left lg:text-right">
          <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400 text-sm">
            <Clock className="w-4 h-4" />
            <span>
              Last updated: {getTimeAgo(healthData.timestamp)}
            </span>
          </div>
          
          {/* Uptime percentage */}
          <div className="mt-2">
            <div className="text-xl sm:text-2xl font-bold text-green-400 dark:text-green-400">
              <AnimatedValue 
                value={Math.round((healthData.total_up / healthData.total_checks) * 100)} 
                suffix="%" 
              />
            </div>
            <div className="text-sm text-gray-700 dark:text-gray-500">uptime</div>
          </div>
        </div>
      </div>

      {/* Sparkline Health Segments */}
      <div className="mt-6">
        <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400 mb-3">
          <span>System Health</span>
          <span>{healthData.total_up}/{healthData.total_checks}</span>
        </div>
        
        {/* Tactical Sparkline Pills */}
        <div className="flex gap-1">
          {[...Array(healthData.total_checks)].map((_, i) => (
            <div
              key={i}
              className={`h-2 flex-1 rounded-full transition-all duration-300 ${
                i < healthData.total_up 
                  ? 'bg-gradient-to-t from-green-500 to-green-400 dark:from-green-500 dark:to-green-400 shadow-sm shadow-green-400/50' 
                  : 'bg-gray-700/50 dark:bg-gray-600/50'
              }`}
              style={{
                animationDelay: `${i * 50}ms`,
                animation: i < healthData.total_up ? 'pulse-glow 2s ease-in-out infinite' : 'none'
              }}
            />
          ))}
        </div>
        
        {/* Layer Breakdown Pills */}
        <div className="flex flex-wrap gap-2 mt-3">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-blue-400/80 dark:bg-blue-400/80"></div>
            <span className="text-xs text-gray-600 dark:text-gray-400">Loopbacks</span>
            <span className="text-xs text-blue-400 dark:text-blue-400 font-mono">
              {healthData.layers?.loopbacks?.up || 0}/{healthData.layers?.loopbacks?.total || 0}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-purple-400/80 dark:bg-purple-400/80"></div>
            <span className="text-xs text-gray-600 dark:text-gray-400">Services</span>
            <span className="text-xs text-purple-400 dark:text-purple-400 font-mono">
              {healthData.layers?.services?.up || 0}/{healthData.layers?.services?.total || 0}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-cyan-400/80 dark:bg-cyan-400/80"></div>
            <span className="text-xs text-gray-600 dark:text-gray-400">Infrastructure</span>
            <span className="text-xs text-cyan-400 dark:text-cyan-400 font-mono">
              {healthData.layers?.infrastructure?.up || 0}/{healthData.layers?.infrastructure?.total || 0}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default HealthOverview
