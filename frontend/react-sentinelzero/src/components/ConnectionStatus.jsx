import React from 'react'
import { useSocket } from '../contexts/SocketContext'
import { AlertTriangle, Wifi, WifiOff } from 'lucide-react'

const ConnectionStatus = () => {
  const { isConnected, isInitialized } = useSocket()

  if (!isInitialized) {
    return (
      <div className="flex items-center space-x-2 text-yellow-400 text-sm">
        <div className="animate-spin rounded-full h-4 w-4 border-2 border-yellow-400 border-t-transparent"></div>
        <span>Connecting...</span>
      </div>
    )
  }

  if (isConnected) {
    return (
      <div className="flex items-center space-x-2 text-green-400 text-sm">
        <Wifi className="h-4 w-4" />
        <span>Connected</span>
      </div>
    )
  }

  return (
    <div className="flex items-center space-x-2 text-red-400 text-sm">
      <WifiOff className="h-4 w-4" />
      <span>Backend Offline</span>
      <AlertTriangle className="h-4 w-4" />
    </div>
  )
}

export default ConnectionStatus
