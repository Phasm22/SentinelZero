import React, { useState, useEffect } from 'react'
import { useSocket } from '../contexts/SocketContext'
import HealthOverview from '../components/lab-status/HealthOverview'
import LayerStatus from '../components/lab-status/LayerStatus'
import HostGrid from '../components/lab-status/HostGrid'

const LabStatus = () => {
  const [healthData, setHealthData] = useState({
    // Start with optimistic/skeleton data
    total_checks: 21,
    total_up: 21,
    overall_health: 'healthy',
    timestamp: new Date().toISOString(),
    layers: {
      loopbacks: { total: 3, up: 3 },
      services: { total: 6, up: 6 },
      infrastructure: { total: 12, up: 12 }
    }
  })
  const [detailedData, setDetailedData] = useState({})
  const [loading, setLoading] = useState(false) // Start with false to show UI immediately
  const [filter, setFilter] = useState('all') // all, loopbacks, services, infrastructure
  const { socket, isConnected } = useSocket()

  // Fetch health summary with timeout
  const fetchHealthData = async () => {
    try {
      const baseUrl = import.meta.env.DEV ? 'http://localhost:5000' : '';
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout
      
      const response = await fetch(`${baseUrl}/api/whatsup/summary`, {
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      
      if (response.ok) {
        const data = await response.json()
        setHealthData(data)
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Failed to fetch health data:', error)
      }
    }
  }

  // Fetch detailed host information with timeout
  const fetchDetailedData = async () => {
    try {
      const baseUrl = import.meta.env.DEV ? 'http://localhost:5000' : '';
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 8000) // 8 second timeout
      
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
    setLoading(false) // Show UI immediately
    
    // Fetch data in background with timeout
    const fetchWithTimeout = async () => {
      try {
        await Promise.race([
          Promise.all([fetchHealthData(), fetchDetailedData()]),
          new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 3000))
        ])
      } catch (error) {
        console.log('Initial fetch timed out, using polling interval')
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
