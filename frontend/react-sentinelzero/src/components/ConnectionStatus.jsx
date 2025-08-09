import React from 'react'
import { useSocket } from '../contexts/SocketContext'
import { AlertTriangle, Wifi, WifiOff } from 'lucide-react'

const ConnectionStatus = () => {
  const { isConnected, isInitialized } = useSocket()

  const baseClasses = 'flex items-center rounded-md px-2 py-1 text-[11px] sm:text-xs font-medium select-none'

  if (!isInitialized) {
    return (
      <div className={`${baseClasses} gap-1 bg-yellow-500/10 text-yellow-400 border border-yellow-500/30`}>
        <div className="animate-spin rounded-full h-3 w-3 border-2 border-yellow-400 border-t-transparent" />
        <span className="hidden xs:inline">Connecting</span>
      </div>
    )
  }

  if (isConnected) {
    return (
      <div className={`${baseClasses} gap-1 bg-green-500/10 text-green-400 border border-green-500/30`}>
        <Wifi className="h-3 w-3 sm:h-4 sm:w-4" />
        <span className="hidden xs:inline">Online</span>
      </div>
    )
  }

  return (
    <div className={`${baseClasses} gap-1 bg-red-500/10 text-red-400 border border-red-500/30`}>
      <WifiOff className="h-3 w-3 sm:h-4 sm:w-4" />
      <span className="hidden xs:inline">Offline</span>
      <AlertTriangle className="h-3 w-3 sm:h-4 sm:w-4" />
    </div>
  )
}

export default ConnectionStatus
