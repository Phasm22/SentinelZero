import React from 'react'
import { CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-react'

const HealthIndicator = ({ 
  status, 
  size = 'sm', 
  showText = false, 
  className = '',
  variant = 'dot' // 'dot', 'pill', 'sparkline'
}) => {
  const getStatusConfig = (status) => {
    switch (status) {
      case 'healthy':
      case 'up':
      case true:
        return {
          color: 'text-green-400',
          bg: 'bg-green-500/20',
          border: 'border-green-500/30',
          icon: CheckCircle,
          text: 'Healthy',
          glow: 'shadow-green-500/20'
        }
      case 'warning':
        return {
          color: 'text-yellow-400',
          bg: 'bg-yellow-500/20',
          border: 'border-yellow-500/30',
          icon: AlertTriangle,
          text: 'Warning',
          glow: 'shadow-yellow-500/20'
        }
      case 'critical':
      case 'down':
      case false:
        return {
          color: 'text-red-400',
          bg: 'bg-red-500/20',
          border: 'border-red-500/30',
          icon: XCircle,
          text: 'Critical',
          glow: 'shadow-red-500/20'
        }
      case 'unknown':
      default:
        return {
          color: 'text-gray-400',
          bg: 'bg-gray-500/20',
          border: 'border-gray-500/30',
          icon: Clock,
          text: 'Unknown',
          glow: 'shadow-gray-500/20'
        }
    }
  }

  const getSizeConfig = (size) => {
    switch (size) {
      case 'xs':
        return { dot: 'w-2 h-2', icon: 'w-3 h-3', text: 'text-xs' }
      case 'sm':
        return { dot: 'w-3 h-3', icon: 'w-4 h-4', text: 'text-sm' }
      case 'md':
        return { dot: 'w-4 h-4', icon: 'w-5 h-5', text: 'text-base' }
      case 'lg':
        return { dot: 'w-6 h-6', icon: 'w-6 h-6', text: 'text-lg' }
      default:
        return { dot: 'w-3 h-3', icon: 'w-4 h-4', text: 'text-sm' }
    }
  }

  const config = getStatusConfig(status)
  const sizeConfig = getSizeConfig(size)
  const Icon = config.icon

  if (variant === 'dot') {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div 
          className={`${sizeConfig.dot} ${config.bg} ${config.border} border rounded-full shadow-lg ${config.glow} animate-pulse`}
        />
        {showText && (
          <span className={`${config.color} ${sizeConfig.text} font-medium`}>
            {config.text}
          </span>
        )}
      </div>
    )
  }

  if (variant === 'pill') {
    return (
      <div className={`inline-flex items-center gap-2 px-3 py-1 ${config.bg} ${config.border} border rounded-full backdrop-blur-sm ${className}`}>
        <Icon className={`${sizeConfig.icon} ${config.color}`} />
        {showText && (
          <span className={`${config.color} ${sizeConfig.text} font-medium`}>
            {config.text}
          </span>
        )}
      </div>
    )
  }

  if (variant === 'sparkline') {
    return (
      <div className={`flex items-center gap-1 ${className}`}>
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className={`w-1 ${config.bg} rounded-full transition-all duration-200`}
            style={{ 
              height: status === 'healthy' ? `${8 + i * 2}px` : '4px',
              opacity: status === 'healthy' ? 1 : 0.3
            }}
          />
        ))}
      </div>
    )
  }

  return null
}

export default HealthIndicator
