import React, { useState, useEffect } from 'react'
import { useSocket } from '../contexts/SocketContext'
import { AlertTriangle, Wifi, WifiOff, Server, Monitor, Database, Globe } from 'lucide-react'
import { apiService } from '../utils/api'

const ConnectionStatus = () => {
  const { isConnected, isInitialized } = useSocket()
  const [backendConnected, setBackendConnected] = useState(false)
  const [backendInitialized, setBackendInitialized] = useState(false)

  const baseClasses = 'flex items-center rounded-md px-2 py-1 text-[11px] sm:text-xs font-medium select-none'

  // Test backend connectivity
  useEffect(() => {
    const testBackendConnection = async () => {
      try {
        const response = await apiService.ping()
        setBackendConnected(response.status === 'success')
        setBackendInitialized(true)
      } catch (error) {
        setBackendConnected(false)
        setBackendInitialized(true)
      }
    }

    testBackendConnection()
    
    // Test backend connection every 30 seconds
    const interval = setInterval(testBackendConnection, 30000)
    
    return () => clearInterval(interval)
  }, [])

  // Frontend socket status component
  const FrontendStatus = () => {
    if (!isInitialized) {
      return (
        <div className={`${baseClasses} gap-1 bg-yellow-500/10 text-yellow-400 border border-yellow-500/30`}>
          <div className="animate-spin rounded-full h-3 w-3 border-2 border-yellow-400 border-t-transparent" />
          <Monitor className="h-3 w-3 sm:h-4 sm:w-4" />
          <span className="hidden xs:inline">Frontend Connecting</span>
        </div>
      )
    }

    if (isConnected) {
      return (
        <div className={`${baseClasses} gap-1 bg-green-500/10 text-green-400 border border-green-500/30`}>
          <Wifi className="h-3 w-3 sm:h-4 sm:w-4" />
          <Monitor className="h-3 w-3 sm:h-4 sm:w-4" />
          <span className="hidden xs:inline">Frontend Online</span>
        </div>
      )
    }

    return (
      <div className={`${baseClasses} gap-1 bg-red-500/10 text-red-400 border border-red-500/30`}>
        <WifiOff className="h-3 w-3 sm:h-4 sm:w-4" />
        <Monitor className="h-3 w-3 sm:h-4 sm:w-4" />
        <span className="hidden xs:inline">Frontend Offline</span>
        <AlertTriangle className="h-3 w-3 sm:h-4 sm:w-4" />
      </div>
    )
  }

  // Backend API status component
  const BackendStatus = () => {
    if (!backendInitialized) {
      return (
        <div className={`${baseClasses} gap-1 bg-yellow-500/10 text-yellow-400 border border-yellow-500/30`}>
          <div className="animate-spin rounded-full h-3 w-3 border-2 border-yellow-400 border-t-transparent" />
          <Server className="h-3 w-3 sm:h-4 sm:w-4" />
          <span className="hidden xs:inline">Backend Connecting</span>
        </div>
      )
    }

    if (backendConnected) {
      return (
        <div className={`${baseClasses} gap-1 bg-green-500/10 text-green-400 border border-green-500/30`}>
          <Database className="h-3 w-3 sm:h-4 sm:w-4" />
          <Server className="h-3 w-3 sm:h-4 sm:w-4" />
          <span className="hidden xs:inline">Backend Online</span>
        </div>
      )
    }

    return (
      <div className={`${baseClasses} gap-1 bg-red-500/10 text-red-400 border border-red-500/30`}>
        <Server className="h-3 w-3 sm:h-4 sm:w-4" />
        <span className="hidden xs:inline">Backend Offline</span>
        <AlertTriangle className="h-3 w-3 sm:h-4 sm:w-4" />
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <FrontendStatus />
      <BackendStatus />
    </div>
  )
}

export default ConnectionStatus
