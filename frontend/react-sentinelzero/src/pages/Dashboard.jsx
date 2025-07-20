import React, { useState, useEffect } from 'react'
import { useSocket } from '../contexts/SocketContext'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import ScanDetailsModal from '../components/ScanDetailsModal'
import AnimatedValue from '../components/AnimatedValue'
import StatCard from '../components/StatCard'
import { 
  Server, 
  Shield, 
  AlertTriangle, 
  Clock,
  Play,
  RefreshCw,
  Eye,
  Trash2,
  Rocket,
  Cpu,
  Bug,
  ShieldCheck,
  Info,
  Loader2
} from 'lucide-react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'
import { formatTimestamp } from '../utils/date'
import ScanControls from '../components/ScanControls'
import RecentScansTable from '../components/RecentScansTable'

const Dashboard = () => {
  const { preferences } = useUserPreferences()
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

  // Accept use24Hour as a prop or fallback to false
  const VulnIcon = ({ count }) =>
    count === 0
      ? <ShieldCheck className="w-7 h-7 text-green-500" />
      : <AlertTriangle className="w-7 h-7 text-red-500 animate-pulse" />

  // Helper for Disconnected dot
  const DisconnectedDot = () => (
    <span className="relative flex h-3 w-3">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
    </span>
  )

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
    <div className="space-y-10 w-full">
      {/* Header with shimmer/progress bar */}
      <div className="relative">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-5xl font-title font-extrabold text-gray-100 tracking-tight drop-shadow-lg">Dashboard</h1>
            <p className="text-lg text-gray-400 mt-2">Network Security Scanner</p>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={clearAllData}
              className="btn btn-error btn-sm flex items-center space-x-2 hover:bg-red-700 hover:text-white transition-colors relative group"
              title="This will wipe all scan history. Are you sure?"
            >
              <Trash2 className="w-6 h-6 text-red-500 group-hover:text-white transition-colors" />
              <span>Clear All Data</span>
            </button>
          </div>
        </div>
        {/* Shimmer/progress bar under header during scan */}
        {isScanning && (
          <div className="absolute left-0 right-0 top-full mt-2 h-1 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 animate-pulse rounded-full shadow-lg" />
        )}
        {isScanning && (
          <div className="flex items-center mt-2">
            <Loader2 className="w-5 h-5 mr-2 animate-spin text-blue-400" />
            <span className="text-blue-300 animate-pulse font-semibold">Scanning…</span>
          </div>
        )}
      </div>

      <ScanControls
        onScanTrigger={handleScanTrigger}
        isScanning={isScanning}
        scanProgress={scanProgress}
        isConnected={isConnected}
      />

      {/* System Info Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon={<Server className="w-8 h-8 text-blue-400 mb-1" />}
          label="Total Scans"
          value={<AnimatedValue value={systemInfo.total_scans || 0} className="text-3xl font-extrabold text-gray-100" />}
          hoverRing="hover:ring-blue-400/40"
        />
        <StatCard
          icon={<Shield className="w-8 h-8 text-green-400 mb-1" />}
          label="Hosts Found"
          value={<AnimatedValue value={systemInfo.hosts_count || 0} className="text-3xl font-extrabold text-gray-100" />}
          hoverRing="hover:ring-green-400/40"
        />
        <StatCard
          icon={VulnIcon({ count: systemInfo.vulns_count })}
          label="Vulnerabilities"
          value={<AnimatedValue value={systemInfo.vulns_count || 0} className={`text-3xl font-extrabold ${systemInfo.vulns_count === 0 ? 'text-green-300' : 'text-red-400'}`} />}
          hoverRing="hover:ring-red-400/40"
        />
        <StatCard
          icon={<Clock className="w-8 h-8 text-yellow-300 mb-1" />}
          label="Last Scan"
          value={<div className="text-xl font-extrabold text-gray-100">{systemInfo.latest_scan_time ? formatTimestamp(systemInfo.latest_scan_time, preferences.use24Hour) : 'Never'}</div>}
          hoverRing="hover:ring-yellow-300/40"
        />
      </div>

      <RecentScansTable
        recentScans={recentScans}
        preferences={preferences}
        handleViewDetails={handleViewDetails}
      />

      {/* Scan Details Modal */}
      <ScanDetailsModal
        scan={selectedScan}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  )
}

export default Dashboard 