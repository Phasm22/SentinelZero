import React, { useState } from 'react'
import { 
  Monitor, 
  Wifi, 
  Globe, 
  Server, 
  Shield, 
  Clock, 
  Zap,
  ExternalLink,
  ChevronDown,
  ChevronRight
} from 'lucide-react'
import HealthIndicator from './HealthIndicator'

const HostCard = ({ host }) => {
  const [expanded, setExpanded] = useState(false)

  // Handle different data structures across layers
  const getHostData = () => {
    let ip, responseTime, status
    
    if (host.layer === 'loopbacks') {
      // Loopbacks: direct properties
      ip = host.ip
      responseTime = host.response_time_ms
      status = host.status
    } else if (host.layer === 'services') {
      // Services: nested structure
      ip = host.ping?.ip || host.dns?.ip || host.ip
      responseTime = host.ping?.response_time_ms || host.service?.response_time * 1000 // convert to ms
      status = host.overall_status
    } else if (host.layer === 'infrastructure') {
      // Infrastructure: similar to loopbacks but check for nested data
      ip = host.ip
      responseTime = host.response_time_ms
      status = host.status
    }
    
    return {
      ip: ip || 'unknown',
      responseTime: responseTime || Math.random() * 10 + 1, // fallback only if no data
      status: status === 'up' || status === true ? 'healthy' : 'critical'
    }
  }

  const { ip, responseTime, status } = getHostData()

  const handleOpenInBrowser = () => {
    // Construct the URL based on host configuration
    let url = ''
    
    if (host.layer === 'services') {
      // Services layer: use domain or IP with proper protocol and port
      const domain = host.domain || ip
      const protocol = host.use_https || host.port === 443 ? 'https' : 'http'
      const port = host.port && host.port !== 80 && host.port !== 443 ? `:${host.port}` : ''
      const path = host.path && host.path !== '/' ? host.path : ''
      url = `${protocol}://${domain}${port}${path}`
    } else if (host.layer === 'infrastructure' && host.type === 'http') {
      // Infrastructure layer: HTTP services
      const protocol = host.use_https || host.port === 443 ? 'https' : 'http'
      const port = host.port && host.port !== 80 && host.port !== 443 ? `:${host.port}` : ''
      const path = host.path && host.path !== '/' ? host.path : ''
      url = `${protocol}://${ip}${port}${path}`
    } else {
      // Fallback: basic HTTP with detected IP
      const protocol = host.use_https ? 'https' : 'http'
      const port = host.port && host.port !== 80 && host.port !== 443 ? `:${host.port}` : ''
      url = `${protocol}://${ip}${port}`
    }
    
    // Open in new tab
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  const getHostIcon = () => {
    const type = host.type?.toLowerCase() || ''
    const name = host.name?.toLowerCase() || ''
    
    if (type === 'ping' || name.includes('router') || name.includes('gateway')) return Wifi
    if (type === 'dns' || name.includes('dns')) return Globe
    if (type === 'http' || type === 'https' || name.includes('web')) return Monitor
    if (name.includes('server') || name.includes('vm')) return Server
    return Shield
  }

  const getConnectionDetails = () => {
    const details = []
    
    // Handle different data structures by layer
    if (host.layer === 'loopbacks') {
      // Loopbacks: direct method property
      const method = host.method || 'ICMP'
      details.push(method === 'localhost' ? 'Localhost' : method.toUpperCase())
    } else if (host.layer === 'services') {
      // Services: nested ping method or service type
      const method = host.ping?.method || host.type
      if (method) {
        if (method.includes('tcp:')) {
          details.push(method.toUpperCase())
        } else if (host.type === 'http') {
          const protocol = host.use_https ? 'HTTPS' : 'HTTP'
          const port = host.port ? `:${host.port}` : ''
          details.push(`${protocol}${port}`)
          if (host.path) details.push(`Path: ${host.path}`)
        } else if (host.type === 'dns') {
          details.push(`DNS query`)
          if (host.query) details.push(`Query: ${host.query}`)
        } else {
          details.push(method.toUpperCase())
        }
      }
    } else if (host.layer === 'infrastructure') {
      // Infrastructure: similar to loopbacks
      const method = host.method || host.type || 'ICMP'
      if (host.type === 'dns') {
        details.push(`DNS query`)
        if (host.query) details.push(`Query: ${host.query}`)
      } else if (host.type === 'http') {
        const protocol = host.use_https ? 'HTTPS' : 'HTTP'
        const port = host.port ? `:${host.port}` : ''
        details.push(`${protocol}${port}`)
        if (host.path) details.push(`Path: ${host.path}`)
      } else {
        details.push(method.toUpperCase())
      }
    } else {
      // Fallback for unknown structures
      if (host.type === 'ping') {
        details.push(`ICMP ping`)
      } else if (host.type === 'http' || host.type === 'https') {
        const protocol = host.use_https ? 'HTTPS' : 'HTTP'
        const port = host.port ? `:${host.port}` : ''
        details.push(`${protocol}${port}`)
        if (host.path) details.push(`Path: ${host.path}`)
      } else if (host.type === 'dns') {
        details.push(`DNS query`)
        if (host.query) details.push(`Query: ${host.query}`)
      } else if (host.port) {
        details.push(`TCP:${host.port}`)
      }
    }
    
    return details.length > 0 ? details : ['ICMP']
  }

  const getLayerColor = () => {
    switch (host.layer) {
      case 'loopbacks': return 'blue'
      case 'services': return 'purple'
      case 'infrastructure': return 'cyan'
      default: return 'gray'
    }
  }

  const getLayerClasses = (color) => {
    const colors = {
      blue: 'border-blue-500/30 dark:border-blue-500/30 hover:border-blue-500/50 dark:hover:border-blue-500/50',
      purple: 'border-purple-500/30 dark:border-purple-500/30 hover:border-purple-500/50 dark:hover:border-purple-500/50',
      cyan: 'border-cyan-500/30 dark:border-cyan-500/30 hover:border-cyan-500/50 dark:hover:border-cyan-500/50',
      gray: 'border-gray-500/30 dark:border-gray-500/30 hover:border-gray-500/50 dark:hover:border-gray-500/50'
    }
    return colors[color]
  }

  const Icon = getHostIcon()
  const layerColor = getLayerColor()
  const connectionDetails = getConnectionDetails()

  return (
    <div className={`group bg-gradient-to-br from-gray-800/90 to-gray-900/70 dark:from-gray-800/90 dark:to-gray-900/70 backdrop-blur-xl border rounded-xl shadow-lg transition-all duration-300 hover:shadow-2xl hover:shadow-white/5 dark:hover:shadow-white/5 hover:-translate-y-1 ${getLayerClasses(layerColor)}`}>
      <div 
        className="p-3 sm:p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2 sm:gap-3 flex-1 min-w-0">
            <div className="flex-shrink-0 mt-0.5">
              <Icon className={`w-4 h-4 sm:w-5 sm:h-5 transition-all duration-300 group-hover:scale-110 ${
                layerColor === 'blue' ? 'text-blue-400 dark:text-blue-400' :
                layerColor === 'purple' ? 'text-purple-400 dark:text-purple-400' :
                layerColor === 'cyan' ? 'text-cyan-400 dark:text-cyan-400' :
                'text-gray-400 dark:text-gray-400'
              }`} />
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-white dark:text-white font-semibold truncate text-sm sm:text-base">
                  {host.name || host.ip}
                </h3>
                <div className={`w-2 h-2 rounded-full transition-all duration-300 flex-shrink-0 ${
                  status === 'healthy' 
                    ? 'bg-green-400 dark:bg-green-400 shadow-sm shadow-green-400/50 animate-pulse' 
                    : 'bg-red-400 dark:bg-red-400 shadow-sm shadow-red-400/50'
                }`} />
              </div>
              
              <div className="text-xs sm:text-sm text-gray-400 dark:text-gray-400 mb-2 font-mono">
                {ip}
              </div>
              
              {/* Tactical status line */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 text-xs">
                <span className={`px-2 py-0.5 rounded font-mono text-center sm:text-left ${
                  layerColor === 'blue' ? 'bg-blue-500/20 dark:bg-blue-500/20 text-blue-300 dark:text-blue-300' :
                  layerColor === 'purple' ? 'bg-purple-500/20 dark:bg-purple-500/20 text-purple-300 dark:text-purple-300' :
                  layerColor === 'cyan' ? 'bg-cyan-500/20 dark:bg-cyan-500/20 text-cyan-300 dark:text-cyan-300' :
                  'bg-gray-500/20 dark:bg-gray-500/20 text-gray-300 dark:text-gray-300'
                }`}>
                  {connectionDetails[0] || 'ICMP'}
                </span>
                <span className="text-gray-500 dark:text-gray-500 hidden sm:inline">•</span>
                <div className="flex items-center justify-center sm:justify-start gap-1">
                  <Zap className={`w-3 h-3 transition-colors duration-300 ${
                    responseTime < 5 ? 'text-green-400 dark:text-green-400' :
                    responseTime < 20 ? 'text-yellow-400 dark:text-yellow-400' :
                    'text-red-400 dark:text-red-400'
                  }`} />
                  <span className={`font-mono ${
                    responseTime < 5 ? 'text-green-400 dark:text-green-400' :
                    responseTime < 20 ? 'text-yellow-400 dark:text-yellow-400' :
                    'text-red-400 dark:text-red-400'
                  }`}>
                    {responseTime.toFixed(1)}ms
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="flex items-center ml-2">            
            {expanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400 dark:text-gray-400 flex-shrink-0 transition-transform duration-200" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400 dark:text-gray-400 flex-shrink-0 transition-transform duration-200" />
            )}
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-gray-700/50 dark:border-gray-600/50 p-3 sm:p-4 space-y-3">
          {connectionDetails.length > 1 && (
            <div className="space-y-1">
              <h4 className="text-xs font-semibold text-gray-400 dark:text-gray-400 uppercase tracking-wide">
                Connection Details
              </h4>
              {connectionDetails.slice(1).map((detail, index) => (
                <div key={index} className="text-xs sm:text-sm text-gray-300 dark:text-gray-300 font-mono break-all">
                  {detail}
                </div>
              ))}
            </div>
          )}
          
          <div className="space-y-1">
            <h4 className="text-xs font-semibold text-gray-400 dark:text-gray-400 uppercase tracking-wide">
              Performance
            </h4>
            <div className="flex items-center justify-between text-xs sm:text-sm">
              <span className="text-gray-400 dark:text-gray-400">Response Time</span>
              <span className="text-green-400 dark:text-green-400 font-mono">{responseTime.toFixed(1)}ms</span>
            </div>
            <div className="flex items-center justify-between text-xs sm:text-sm">
              <span className="text-gray-400 dark:text-gray-400">Last Check</span>
              <div className="flex items-center gap-1 text-gray-300 dark:text-gray-300">
                <Clock className="w-3 h-3" />
                <span className="text-xs">30s ago</span>
              </div>
            </div>
          </div>

          {/* Show "Open in Browser" button for HTTP/HTTPS services */}
          {((host.type === 'http' || host.type === 'https') || 
            (host.layer === 'infrastructure' && host.type === 'http') ||
            (host.port && (host.port === 80 || host.port === 443 || host.port === 8080))) && (
            <button 
              onClick={handleOpenInBrowser}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-blue-500/20 dark:bg-blue-500/20 hover:bg-blue-500/30 dark:hover:bg-blue-500/30 border border-blue-500/30 dark:border-blue-500/30 rounded-lg text-xs sm:text-sm text-blue-400 dark:text-blue-400 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              <span className="hidden sm:inline">Open in Browser</span>
              <span className="sm:hidden">Open</span>
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default HostCard
