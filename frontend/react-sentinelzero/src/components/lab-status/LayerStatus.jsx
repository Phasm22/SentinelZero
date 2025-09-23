import React from 'react'
import { Wifi, Globe, Server, Filter } from 'lucide-react'
import HealthIndicator from './HealthIndicator'

const LayerStatus = ({ healthData, filter, setFilter }) => {
  if (!healthData?.layers) return null

  const layers = [
    {
      key: 'loopbacks',
      name: 'Loopbacks',
      icon: Wifi,
      description: 'Network health probes',
      data: healthData.layers.loopbacks,
      color: 'blue'
    },
    {
      key: 'services',
      name: 'Services',
      icon: Globe,
      description: 'DNS & application health',
      data: healthData.layers.services,
      color: 'purple'
    },
    {
      key: 'infrastructure',
      name: 'Infrastructure',
      icon: Server,
      description: 'Critical components',
      data: healthData.layers.infrastructure,
      color: 'cyan'
    }
  ]

  const getLayerStatus = (layer) => {
    if (layer.up === layer.total) return 'healthy'
    if (layer.up > layer.total * 0.8) return 'warning'
    return 'critical'
  }

  const getColorClasses = (color, isActive) => {
    const colors = {
      blue: {
        border: isActive ? 'border-blue-500/50 dark:border-blue-500/50' : 'border-blue-500/20 dark:border-blue-500/20',
        bg: isActive ? 'bg-blue-500/20 dark:bg-blue-500/20' : 'bg-blue-500/10 dark:bg-blue-500/10',
        text: 'text-blue-400 dark:text-blue-400',
        glow: isActive ? 'shadow-blue-500/20 dark:shadow-blue-500/20' : 'shadow-blue-500/10 dark:shadow-blue-500/10'
      },
      purple: {
        border: isActive ? 'border-purple-500/50 dark:border-purple-500/50' : 'border-purple-500/20 dark:border-purple-500/20',
        bg: isActive ? 'bg-purple-500/20 dark:bg-purple-500/20' : 'bg-purple-500/10 dark:bg-purple-500/10',
        text: 'text-purple-400 dark:text-purple-400',
        glow: isActive ? 'shadow-purple-500/20 dark:shadow-purple-500/20' : 'shadow-purple-500/10 dark:shadow-purple-500/10'
      },
      cyan: {
        border: isActive ? 'border-cyan-500/50 dark:border-cyan-500/50' : 'border-cyan-500/20 dark:border-cyan-500/20',
        bg: isActive ? 'bg-cyan-500/20 dark:bg-cyan-500/20' : 'bg-cyan-500/10 dark:bg-cyan-500/10',
        text: 'text-cyan-400 dark:text-cyan-400',
        glow: isActive ? 'shadow-cyan-500/20 dark:shadow-cyan-500/20' : 'shadow-cyan-500/10 dark:shadow-cyan-500/10'
      }
    }
    return colors[color]
  }

  return (
    <div className="space-y-4">
      {/* Filter selector */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
        <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
          <Filter className="w-4 h-4" />
          <span className="text-sm font-medium">Filter:</span>
        </div>
        <button
          onClick={() => setFilter(filter === 'all' ? 'loopbacks' : 'all')}
          className={`px-3 py-1 rounded-md text-sm font-medium transition-all duration-200 self-start ${
            filter === 'all' 
              ? 'bg-gray-800/80 dark:bg-white/20 text-gray-100 dark:text-white border border-gray-600/50 dark:border-white/30 shadow-lg' 
              : 'bg-blue-600/60 dark:bg-blue-500/20 text-blue-100 dark:text-blue-300 border border-blue-500/60 dark:border-blue-400/40 shadow-lg shadow-blue-500/20'
          }`}
          title="Click to toggle all layers or choose a specific layer below"
        >
          {(() => {
            const labels = {
              all: 'All Layers',
              loopbacks: 'Loopbacks',
              services: 'Services',
              infrastructure: 'Infrastructure'
            }
            return `Viewing: ${labels[filter]}`
          })()}
        </button>
      </div>

      {/* Tactical Layer Pills */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
        {layers.map((layer) => {
          const isActive = filter === layer.key || filter === 'all'
          const colorClasses = getColorClasses(layer.color, isActive)
          const status = getLayerStatus(layer.data)
          const Icon = layer.icon

          return (
            <button
              key={layer.key}
              onClick={() => setFilter(filter === layer.key ? 'all' : layer.key)}
              className={`group p-4 rounded-lg border backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl cursor-pointer ${
                colorClasses.bg
              } ${colorClasses.border} shadow-lg ${colorClasses.glow} ${
                isActive ? 'ring-1 ring-white/30 dark:ring-white/30 shadow-xl' : ''
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-3 sm:space-y-0">
                <div className="flex items-center gap-3">
                  <Icon className={`w-5 h-5 sm:w-6 sm:h-6 transition-transform duration-300 group-hover:scale-110 ${colorClasses.text}`} />
                  <div className="text-left">
                    <div className="text-white dark:text-white font-semibold text-sm sm:text-base">{layer.name}</div>
                    <div className="text-xs text-gray-400 dark:text-gray-400">{layer.description}</div>
                  </div>
                </div>
                
                <div className="flex items-center justify-between sm:justify-end gap-3">
                  <div className="text-left sm:text-right">
                    <div className={`text-base sm:text-lg font-bold font-mono transition-colors duration-300 ${
                      status === 'healthy' ? 'text-green-400 dark:text-green-400' :
                      status === 'warning' ? 'text-yellow-400 dark:text-yellow-400' :
                      'text-red-400 dark:text-red-400'
                    }`}>
                      {layer.data.up}/{layer.data.total}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-500">
                      {Math.round((layer.data.up / layer.data.total) * 100)}% up
                    </div>
                  </div>
                </div>
              </div>

              {/* Tactical Sparkline Pills */}
              <div className="mt-3 flex gap-0.5">
                {[...Array(layer.data.total)].map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 flex-1 rounded-full transition-all duration-300 ${
                      i < layer.data.up 
                        ? `${status === 'healthy' ? 'bg-green-400 dark:bg-green-400 shadow-sm shadow-green-400/50' :
                            status === 'warning' ? 'bg-yellow-400 dark:bg-yellow-400 shadow-sm shadow-yellow-400/50' :
                            'bg-red-400 dark:bg-red-400 shadow-sm shadow-red-400/50'}` 
                        : 'bg-gray-700/50 dark:bg-gray-600/50'
                    }`}
                    style={{
                      animationDelay: `${i * 100}ms`,
                      animation: i < layer.data.up ? 'pulse-glow 3s ease-in-out infinite' : 'none'
                    }}
                  />
                ))}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default LayerStatus
