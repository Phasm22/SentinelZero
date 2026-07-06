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
    <div className="card-glass p-4">
      <div className="flex items-center gap-3 mb-4">
        <Globe className="w-5 h-5 text-gray-300" />
        <h3 className="card-heading text-lg">Network Connectivity</h3>
        <div className="flex-1 h-px bg-gradient-to-r from-gray-600/60 to-transparent" />
        <span className="card-meta">
          {hosts.length} {hosts.length === 1 ? 'scanner' : 'scanners'}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
        {hosts.map((host, index) => {
          const Icon = getScannerIcon(host.name)
          const colorClass = getScannerColor(host.name)
          const status = host.status === 'up' || host.status === true ? 'healthy' : 'critical'
          const responseTime = host.response_time_ms || host.ping?.response_time_ms || 0

          return (
            <div
              key={`${host.ip}-${index}`}
              className="card-inner-tile p-3 hover:bg-gray-700/50 transition-all duration-200"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Icon className={`w-4 h-4 ${colorClass}`} />
                  <span className="card-heading text-sm">
                    {host.name}
                  </span>
                </div>
                <HealthIndicator status={status} size="xs" />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between card-meta">
                  <span>IP</span>
                  <span className="text-gray-200 font-mono">{host.ip}</span>
                </div>
                <div className="flex items-center justify-between card-meta">
                  <span>Type</span>
                  <span className="text-gray-200">{host.type || 'ICMP'}</span>
                </div>
                <div className="flex items-center justify-between card-meta">
                  <span>Latency</span>
                  <span className="text-gray-200 font-mono">
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
