import React, { useState, useEffect } from 'react'
import { useSocket } from '../contexts/SocketContext'
import LabHealthBar from '../components/lab-status/LabHealthBar'
import LabOverview from '../components/lab-status/LabOverview'
import HostGrid from '../components/lab-status/HostGrid'
import LabPanel from '../components/lab-status/LabPanel'

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

      return () => {
        console.log('Cleaning up socket listeners')
        socket.off('whats_up.snapshot', handleHealthUpdate)
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
        <LabPanel>
          <div className="flex items-center justify-center space-x-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 dark:border-blue-400" />
            <span className="text-gray-600 dark:text-gray-300">Loading network health status...</span>
          </div>
        </LabPanel>
      )}
      
      <LabHealthBar healthData={healthData} filter={filter} setFilter={setFilter} />
      
      <LabOverview healthData={healthData} detailedData={detailedData} />
      
      <HostGrid 
        detailedData={detailedData} 
        filter={filter} 
      />
    </div>
  )
}

export default LabStatus
