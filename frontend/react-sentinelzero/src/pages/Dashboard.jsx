import React, { useState, useEffect } from 'react'
import { useSocket } from '../contexts/SocketContext'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import ScanDetailsModal from '../components/ScanDetailsModal'
import { 
  Server, 
  Shield, 
  AlertTriangle, 
  Clock,
  Play,
  RefreshCw,
  Eye,
  Trash2
} from 'lucide-react'

const Dashboard = () => {
  const [recentScans, setRecentScans] = useState([])
  const [systemInfo, setSystemInfo] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isScanning, setIsScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState(null)
  const [scanStartTime, setScanStartTime] = useState(null)
  const [selectedScan, setSelectedScan] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const { socket, isConnected, isInitialized } = useSocket()
  const { showToast } = useToast()

  const loadDashboardData = async () => {
    try {
      const [scansData, statsData] = await Promise.all([
        apiService.getScanHistory(),
        apiService.getDashboardStats()
      ])
      
      setRecentScans(scansData.scans || [])
      setSystemInfo(statsData)
      setIsLoading(false)
    } catch (error) {
      console.error('Error loading dashboard data:', error)
      setError('Failed to load dashboard data')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDashboardData()
  }, [])

  useEffect(() => {
    if (!socket || !isInitialized) return

    const handleScanLog = (data) => {
      console.log('📝 Scan log:', data.msg)
    }

    const handleScanProgress = (data) => {
      console.log('📊 Scan progress:', data.percent)
      setScanProgress(data.percent)
    }

    const handleScanComplete = () => {
      console.log('✅ Scan completed')
      setIsScanning(false)
      setScanProgress(null)
      setScanStartTime(null)
      loadDashboardData()
      showToast('Scan completed successfully', 'success')
    }

    const handleScanStart = () => {
      console.log('🚀 Scan started')
      setIsScanning(true)
      setScanProgress(0)
      setScanStartTime(Date.now())
    }

    socket.on('scan_log', handleScanLog)
    socket.on('scan_progress', handleScanProgress)
    socket.on('scan_complete', handleScanComplete)
    socket.on('scan_start', handleScanStart)

    return () => {
      socket.off('scan_log', handleScanLog)
      socket.off('scan_progress', handleScanProgress)
      socket.off('scan_complete', handleScanComplete)
      socket.off('scan_start', handleScanStart)
    }
  }, [socket, isInitialized, showToast])

  const handleScanTrigger = async (scanType) => {
    try {
      setIsScanning(true)
      setScanProgress(0)
      setScanStartTime(Date.now())
      await apiService.triggerScan(scanType)
      showToast(`${scanType} started`, 'info')
    } catch (error) {
      console.error('Error triggering scan:', error)
      setIsScanning(false)
      setScanProgress(null)
      setScanStartTime(null)
      showToast('Failed to start scan', 'danger')
    }
  }

  const handleViewDetails = (scan) => {
    setSelectedScan(scan)
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setSelectedScan(null)
  }

  const clearAllData = async () => {
    if (window.confirm('Are you sure you want to clear all data? This action cannot be undone.')) {
      try {
        await apiService.clearAllData()
        showToast('All data cleared successfully', 'success')
        loadDashboardData()
      } catch (error) {
        console.error('Error clearing data:', error)
        showToast('Failed to clear data', 'danger')
      }
    }
  }

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="mx-auto h-12 w-12 text-red-500" />
        <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">Error</h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400">Network Security Scanner</p>
        </div>
        <div className="flex items-center space-x-4">
          <button
            onClick={clearAllData}
            className="btn btn-outline btn-sm flex items-center space-x-1"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear All Data</span>
          </button>
        </div>
      </div>

      {/* Scan Controls */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">Scan Controls</h2>
          <div className="flex items-center space-x-2">
            {!isConnected && (
              <div className="flex items-center space-x-2 text-yellow-600 dark:text-yellow-400">
                <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                <span className="text-sm">Disconnected</span>
              </div>
            )}
          </div>
        </div>
        
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => handleScanTrigger('Full TCP')}
            disabled={isScanning}
            className="btn btn-primary flex items-center space-x-2"
          >
            {isScanning ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span>{isScanning ? 'Scanning...' : 'Full TCP Scan'}</span>
          </button>
          
          <button
            onClick={() => handleScanTrigger('IoT Scan')}
            disabled={isScanning}
            className="btn btn-outline flex items-center space-x-2"
          >
            <Play className="w-4 h-4" />
            <span>IoT Scan</span>
          </button>
          
          <button
            onClick={() => handleScanTrigger('Vuln Scripts')}
            disabled={isScanning}
            className="btn btn-outline flex items-center space-x-2"
          >
            <Play className="w-4 h-4" />
            <span>Vuln Scripts</span>
          </button>
        </div>

        {/* Progress Bar */}
        {isScanning && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Scan in Progress...
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {scanProgress ? `${Math.round(scanProgress)}%` : '0%'}
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div 
                className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${scanProgress || 0}%` }}
              ></div>
            </div>
          </div>
        )}
      </div>

      {/* System Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center">
            <Server className="h-8 w-8 text-blue-500" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Scans</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {systemInfo.total_scans || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center">
            <Shield className="h-8 w-8 text-green-500" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Hosts Found</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {systemInfo.total_hosts || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center">
            <AlertTriangle className="h-8 w-8 text-red-500" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Vulnerabilities</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {systemInfo.total_vulns || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center">
            <Clock className="h-8 w-8 text-purple-500" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Last Scan</p>
              <p className="text-sm font-bold text-gray-900 dark:text-white">
                {systemInfo.last_scan || 'Never'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Scans */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">Recent Scans</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Hosts</th>
                <th>Vulns</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {recentScans.map((scan) => (
                <tr key={scan.id}>
                  <td>{formatTimestamp(scan.timestamp)}</td>
                  <td>
                    <span className="badge badge-primary">
                      {scan.scan_type}
                    </span>
                  </td>
                  <td>{scan.hosts_count || 0}</td>
                  <td>{scan.vulns_count || 0}</td>
                  <td>
                    <button 
                      onClick={() => handleViewDetails(scan)}
                      className="btn btn-outline btn-sm flex items-center space-x-1"
                    >
                      <Eye className="w-4 h-4" />
                      <span>View</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Scan Details Modal */}
      {isModalOpen && selectedScan && (
        <ScanDetailsModal
          scan={selectedScan}
          onClose={handleCloseModal}
        />
      )}
    </div>
  )
}

export default Dashboard 