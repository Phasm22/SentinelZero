import React, { useState, useEffect } from 'react'
import { useSocket } from '../contexts/SocketContext'
import HealthOverview from '../components/lab-status/HealthOverview'
import LabOverview from '../components/lab-status/LabOverview'
import LayerStatus from '../components/lab-status/LayerStatus'
import HostGrid from '../components/lab-status/HostGrid'

const initialHealthData = {
  total_checks: 0,
  total_up: 0,
  overall_status: 'unknown',
  health_percentage: 0,
  timestamp: new Date().toISOString(),
  layers: {
    loopbacks: { total: 0, up: 0 },
    services: { total: 0, up: 0 },
    infrastructure: { total: 0, up: 0 }
  },
  categories: {
    loopbacks: { items: [] },
    services: { items: [] },
    infrastructure: { items: [] }
  }
}

const normalizeSnapshot = (data = {}) => ({
  ...initialHealthData,
  ...data,
  total_checks: Number.isFinite(data.total_checks) ? data.total_checks : 0,
  total_up: Number.isFinite(data.total_up) ? data.total_up : 0,
  health_percentage: Number.isFinite(data.health_percentage) ? data.health_percentage : 0,
  layers: {
    loopbacks: {
      total: Number.isFinite(data.layers?.loopbacks?.total) ? data.layers.loopbacks.total : 0,
      up: Number.isFinite(data.layers?.loopbacks?.up) ? data.layers.loopbacks.up : 0
    },
    services: {
      total: Number.isFinite(data.layers?.services?.total) ? data.layers.services.total : 0,
      up: Number.isFinite(data.layers?.services?.up) ? data.layers.services.up : 0
    },
    infrastructure: {
      total: Number.isFinite(data.layers?.infrastructure?.total) ? data.layers.infrastructure.total : 0,
      up: Number.isFinite(data.layers?.infrastructure?.up) ? data.layers.infrastructure.up : 0
    }
  },
  categories: {
    loopbacks: { items: data.categories?.loopbacks?.items || [] },
    services: { items: data.categories?.services?.items || [] },
    infrastructure: { items: data.categories?.infrastructure?.items || [] }
  }
})

const LabStatus = () => {
  const [healthData, setHealthData] = useState(initialHealthData)
  const [detailedData, setDetailedData] = useState({
    loopbacks: [],
    services: [],
    infrastructure: []
  })
  const [loading, setLoading] = useState(true) // Start with loading true
  const [filter, setFilter] = useState('all') // all, loopbacks, services, infrastructure
  const { socket, isConnected } = useSocket()

  const applySnapshot = (snapshot) => {
    const safeData = normalizeSnapshot(snapshot)
    setHealthData(safeData)
    setDetailedData({
      loopbacks: safeData.categories.loopbacks.items,
      services: safeData.categories.services.items,
      infrastructure: safeData.categories.infrastructure.items
    })
    setLoading(false)
  }

  const fetchSnapshot = async () => {
    try {
      const baseUrl = window.location.origin
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000)
      
      const response = await fetch(`${baseUrl}/api/whatsup/summary`, {
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      
      if (response.ok) {
        const data = await response.json()
        applySnapshot(data)
      } else {
        setLoading(false)
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Failed to fetch health data:', error)
      }
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)

    const fetchWithTimeout = async () => {
      try {
        await Promise.race([
          fetchSnapshot(),
          new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 15000))
        ])
      } catch (error) {
        console.log('Initial fetch timed out, using polling interval')
        setLoading(false)
      }
    }
    
    fetchWithTimeout()

    // Longer polling interval to reduce server load
    const interval = setInterval(() => {
      fetchSnapshot()
    }, 60000)

    return () => clearInterval(interval)
  }, [])

  // Socket.IO real-time updates
  useEffect(() => {
    if (socket && isConnected) {
      console.log('Setting up socket listeners for health updates')
      
      const handleHealthUpdate = (data) => {
        console.log('Received health update:', data)
        applySnapshot(data)
      }

      socket.on('whats_up.snapshot', handleHealthUpdate)
      socket.on('whats_up_update', handleHealthUpdate)
      socket.on('health_update', handleHealthUpdate)

      return () => {
        console.log('Cleaning up socket listeners')
        socket.off('whats_up.snapshot', handleHealthUpdate)
        socket.off('whats_up_update', handleHealthUpdate)
        socket.off('health_update', handleHealthUpdate)
      }
    } else if (socket && !isConnected) {
      console.log('Socket exists but not connected yet')
    } else {
      console.log('Socket not available yet')
    }
  }, [socket, isConnected])

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      {/* Loading State */}
      {loading && (
        <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 dark:from-gray-800/80 dark:to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-6">
          <div className="flex items-center justify-center space-x-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400"></div>
            <span className="text-gray-300">Loading network health status...</span>
          </div>
        </div>
      )}
      
      {/* Health Overview */}
      <HealthOverview healthData={healthData} />
      
      {/* Lab Network Overview */}
      <LabOverview healthData={healthData} detailedData={detailedData} />
      
      {/* Layer Status Pills */}
      <LayerStatus 
        healthData={healthData} 
        filter={filter} 
        setFilter={setFilter} 
      />
      
      {/* Host Grid */}
      <HostGrid 
        detailedData={detailedData} 
        filter={filter} 
      />
    </div>
  )
}

export default LabStatus
