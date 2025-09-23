import React from 'react'
import { Activity, Server, Wifi, Globe, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import HealthIndicator from './HealthIndicator'
import AnimatedValue from '../AnimatedValue'

const LabOverview = ({ healthData, detailedData }) => {
  if (!healthData || !detailedData) return null

  // Calculate network segment health
  const getSegmentHealth = (hosts) => {
    if (!hosts || hosts.length === 0) return { status: 'unknown', count: 0, total: 0 }
    const up = hosts.filter(host => host.status === 'up' || host.status === true).length
    const total = hosts.length
    const status = up === total ? 'healthy' : up > total * 0.8 ? 'warning' : 'critical'
    return { status, count: up, total }
  }

  // Get all hosts from detailed data
  const allHosts = [
    ...(detailedData.loopbacks || []),
    ...(detailedData.services || []),
    ...(detailedData.infrastructure || [])
  ]

  // Calculate segment health
  const labNetwork = allHosts.filter(host => {
    const ip = host.ip || host.ping?.ip || host.dns?.ip || 'unknown'
    return ip.startsWith('172.16.') || ip.startsWith('192.168.71.')
  })
  
  const homeNetwork = allHosts.filter(host => {
    const ip = host.ip || host.ping?.ip || host.dns?.ip || 'unknown'
    return ip.startsWith('192.168.68.')
  })

  const externalServices = allHosts.filter(host => {
    const ip = host.ip || host.ping?.ip || host.dns?.ip || 'unknown'
    return ip.match(/^(1\.1\.1\.|8\.8\.8\.|208\.67\.)/) || 
           host.name?.includes('Cloudflare') || 
           host.name?.includes('Google DNS') || 
           host.name?.includes('Internet Test')
  })

  const labHealth = getSegmentHealth(labNetwork)
  const homeHealth = getSegmentHealth(homeNetwork)
  const externalHealth = getSegmentHealth(externalServices)

  const segments = [
    {
      name: 'Lab Infrastructure',
      icon: Server,
      color: 'blue',
      health: labHealth,
      description: 'Proxmox, VMs, and lab services'
    },
    {
      name: 'Home Network',
      icon: Wifi,
      color: 'green',
      health: homeHealth,
      description: 'Home devices and services'
    },
    {
      name: 'External Services',
      icon: Globe,
      color: 'purple',
      health: externalHealth,
      description: 'DNS and internet connectivity'
    }
  ]

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return CheckCircle
      case 'warning': return AlertTriangle
      case 'critical': return XCircle
      default: return Activity
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-green-400'
      case 'warning': return 'text-yellow-400'
      case 'critical': return 'text-red-400'
      default: return 'text-gray-400'
    }
  }

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 dark:from-gray-800/80 dark:to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-lg shadow-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <Activity className="w-6 h-6 text-blue-400 dark:text-blue-400" />
        <h2 className="text-xl font-bold text-gray-200 dark:text-gray-200">Lab Network Overview</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {segments.map((segment) => {
          const StatusIcon = getStatusIcon(segment.health.status)
          const colorClass = getStatusColor(segment.health.status)
          const Icon = segment.icon

          return (
            <div
              key={segment.name}
              className="bg-gray-700/40 dark:bg-gray-700/40 border border-gray-600/30 dark:border-gray-600/30 rounded-lg p-4 hover:bg-gray-700/60 dark:hover:bg-gray-700/60 transition-all duration-200"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Icon className="w-5 h-5 text-gray-300 dark:text-gray-300" />
                  <span className="font-semibold text-gray-200 dark:text-gray-200">{segment.name}</span>
                </div>
                <StatusIcon className={`w-5 h-5 ${colorClass}`} />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400 dark:text-gray-400">Status</span>
                  <HealthIndicator status={segment.health.status} size="sm" showText />
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400 dark:text-gray-400">Hosts</span>
                  <span className="text-sm text-gray-300 dark:text-gray-300 font-mono">
                    <AnimatedValue value={segment.health.count} />/{segment.health.total}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400 dark:text-gray-400">Health</span>
                  <span className="text-sm text-gray-300 dark:text-gray-300">
                    {segment.health.total > 0 ? Math.round((segment.health.count / segment.health.total) * 100) : 0}%
                  </span>
                </div>
              </div>

              <div className="mt-3">
                <div className="text-xs text-gray-500 dark:text-gray-500">{segment.description}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Network Health Sparkline */}
      <div className="mt-6 pt-4 border-t border-gray-600/30 dark:border-gray-600/30">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-gray-400 dark:text-gray-400">Network Health Distribution</span>
          <span className="text-xs text-gray-500 dark:text-gray-500">
            {allHosts.length} total hosts
          </span>
        </div>
        
        <div className="flex gap-1">
          {allHosts.map((host, index) => {
            const isUp = host.status === 'up' || host.status === true
            return (
              <div
                key={`${host.ip}-${index}`}
                className={`h-2 flex-1 rounded-full transition-all duration-300 ${
                  isUp 
                    ? 'bg-gradient-to-t from-green-500 to-green-400 dark:from-green-500 dark:to-green-400 shadow-sm shadow-green-400/50' 
                    : 'bg-gray-700/50 dark:bg-gray-600/50'
                }`}
                style={{
                  animationDelay: `${index * 20}ms`,
                  animation: isUp ? 'pulse-glow 2s ease-in-out infinite' : 'none'
                }}
                title={`${host.name || host.ip}: ${isUp ? 'UP' : 'DOWN'}`}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default LabOverview
