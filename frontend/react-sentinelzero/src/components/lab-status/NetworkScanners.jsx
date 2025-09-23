import React from 'react'
import { Globe, Zap, Shield } from 'lucide-react'
import HealthIndicator from './HealthIndicator'

const NetworkScanners = ({ hosts }) => {
  if (!hosts || hosts.length === 0) return null

  const getScannerIcon = (name) => {
    if (name.includes('Cloudflare')) return Shield
    if (name.includes('Google')) return Globe
    return Zap
  }

  const getScannerColor = (name) => {
    if (name.includes('Cloudflare')) return 'text-blue-400'
    if (name.includes('Google')) return 'text-green-400'
    return 'text-purple-400'
  }

  return (
    <div className="bg-gradient-to-br from-slate-800/60 to-slate-900/40 dark:from-slate-800/60 dark:to-slate-900/40 backdrop-blur-lg border border-slate-600/30 dark:border-slate-600/30 rounded-lg shadow-lg p-4">
      <div className="flex items-center gap-3 mb-4">
        <Globe className="w-5 h-5 text-slate-300 dark:text-slate-300" />
        <h3 className="text-lg font-semibold text-slate-200 dark:text-slate-200">Network Connectivity</h3>
        <div className="flex-1 h-px bg-gradient-to-r from-slate-600 dark:from-slate-600 to-transparent"></div>
        <span className="text-sm text-slate-400 dark:text-slate-400">
          {hosts.length} {hosts.length === 1 ? 'scanner' : 'scanners'}
        </span>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {hosts.map((host, index) => {
          const Icon = getScannerIcon(host.name)
          const colorClass = getScannerColor(host.name)
          const status = host.status === 'up' || host.status === true ? 'healthy' : 'critical'
          const responseTime = host.response_time_ms || host.ping?.response_time_ms || 0
          
          return (
            <div
              key={`${host.ip}-${index}`}
              className="bg-slate-700/40 dark:bg-slate-700/40 border border-slate-500/30 dark:border-slate-500/30 rounded-lg p-3 hover:bg-slate-700/60 dark:hover:bg-slate-700/60 transition-all duration-200"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Icon className={`w-4 h-4 ${colorClass}`} />
                  <span className="text-sm font-medium text-slate-200 dark:text-slate-200">
                    {host.name}
                  </span>
                </div>
                <HealthIndicator status={status} size="xs" />
              </div>
              
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 dark:text-slate-400">IP</span>
                  <span className="text-slate-300 dark:text-slate-300 font-mono">{host.ip}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 dark:text-slate-400">Type</span>
                  <span className="text-slate-300 dark:text-slate-300">{host.type || 'ICMP'}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 dark:text-slate-400">Latency</span>
                  <span className="text-slate-300 dark:text-slate-300 font-mono">
                    {responseTime ? `${responseTime.toFixed(1)}ms` : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default NetworkScanners
