import React, { useState, useEffect } from 'react'
import { useSocket } from '../contexts/SocketContext'
import HealthOverview from '../components/lab-status/HealthOverview'
import LayerStatus from '../components/lab-status/LayerStatus'
import HostGrid from '../components/lab-status/HostGrid'

const LabStatus = () => {
  const [healthData, setHealthData] = useState({
    // Start with safe defaults to prevent NaN errors
    total_checks: 0,
    total_up: 0,
    overall_health: 'unknown',
    timestamp: new Date().toISOString(),
    layers: {
      loopbacks: { total: 0, up: 0 },
      services: { total: 0, up: 0 },
      infrastructure: { total: 0, up: 0 }
    }
  })
  const [detailedData, setDetailedData] = useState({})
  const [loading, setLoading] = useState(true) // Start with loading true
  const [filter, setFilter] = useState('all') // all, loopbacks, services, infrastructure
  const { socket, isConnected } = useSocket()

  // Fetch health summary with timeout
  const fetchHealthData = async () => {
    try {
      // Use current hostname for API calls when accessed via domain
      const baseUrl = import.meta.env.DEV 
        ? (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
           ? 'http://localhost:5000' 
           : `http://${window.location.hostname}:5000`)
        : '';
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 15000) // 15 second timeout for proxy latency
      
      const response = await fetch(`${baseUrl}/api/whatsup/summary`, {
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      
      if (response.ok) {
        const data = await response.json()
        // Ensure numeric values are safe
        const safeData = {
          ...data,
          total_up: Number.isFinite(data.total_up) ? data.total_up : 0,
          total_checks: Number.isFinite(data.total_checks) ? data.total_checks : 0,
          layers: {
            loopbacks: {
              up: Number.isFinite(data.layers?.loopbacks?.up) ? data.layers.loopbacks.up : 0,
              total: Number.isFinite(data.layers?.loopbacks?.total) ? data.layers.loopbacks.total : 0
            },
            services: {
              up: Number.isFinite(data.layers?.services?.up) ? data.layers.services.up : 0,
              total: Number.isFinite(data.layers?.services?.total) ? data.layers.services.total : 0
            },
            infrastructure: {
              up: Number.isFinite(data.layers?.infrastructure?.up) ? data.layers.infrastructure.up : 0,
              total: Number.isFinite(data.layers?.infrastructure?.total) ? data.layers.infrastructure.total : 0
            }
          }
        }
        setHealthData(safeData)
        setLoading(false)
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

  // Fetch detailed host information with timeout
  const fetchDetailedData = async () => {
    try {
      // Use current hostname for API calls when accessed via domain
      const baseUrl = import.meta.env.DEV 
        ? (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
           ? 'http://localhost:5000' 
           : `http://${window.location.hostname}:5000`)
        : '';
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 20000) // 20 second timeout for proxy latency
      
      const requests = [
        fetch(`${baseUrl}/api/whatsup/loopbacks`, { signal: controller.signal }),
        fetch(`${baseUrl}/api/whatsup/services`, { signal: controller.signal }),
        fetch(`${baseUrl}/api/whatsup/infrastructure`, { signal: controller.signal })
      ]
      
      const responses = await Promise.all(requests)
      clearTimeout(timeoutId)
      
      const [loopbacks, services, infrastructure] = await Promise.all(
        responses.map(r => r.ok ? r.json() : {})
      )
      
      setDetailedData({
        loopbacks: loopbacks.loopbacks || [],
        services: services.services || [],
        infrastructure: infrastructure.infrastructure || []
      })
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Failed to fetch detailed data:', error)
      }
    }
  }

  useEffect(() => {
    // Load immediately with fast timeout, show stale data quickly
    setLoading(true) // Show loading state initially
    
    // Fetch data in background with timeout
    const fetchWithTimeout = async () => {
      try {
        await Promise.race([
          Promise.all([fetchHealthData(), fetchDetailedData()]),
          new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 25000)) // 25 second initial timeout
        ])
      } catch (error) {
        console.log('Initial fetch timed out, using polling interval')
        setLoading(false)
      }
    }
    
    fetchWithTimeout()

    // Longer polling interval to reduce server load
    const interval = setInterval(() => {
      fetchHealthData()
      fetchDetailedData()
    }, 60000) // Poll every 60 seconds instead of 30

    return () => clearInterval(interval)
  }, [])

  // Socket.IO real-time updates
  useEffect(() => {
    if (socket && isConnected) {
      console.log('Setting up socket listeners for health updates')
      
      const handleHealthUpdate = (data) => {
        console.log('Received health update:', data)
        setHealthData(data)
      }

      socket.on('health_update', handleHealthUpdate)

      return () => {
        console.log('Cleaning up socket listeners')
        socket.off('health_update', handleHealthUpdate)
      }
    } else if (socket && !isConnected) {
      console.log('Socket exists but not connected yet')
    } else {
      console.log('Socket not available yet')
    }
  }, [socket, isConnected])

  return (
    <div className="p-3 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      {/* Loading State */}
      {loading && (
        <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 dark:from-gray-800/80 dark:to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-6">
          <div className="flex items-center justify-center space-x-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400"></div>
            <span className="text-gray-300">Loading network health status...</span>
          </div>
        </div>
      )}
      
      {/* Health Overview */}
      <HealthOverview healthData={healthData} />
      
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
