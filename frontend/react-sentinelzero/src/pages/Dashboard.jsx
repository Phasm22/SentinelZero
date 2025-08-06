import React, { useState, useEffect, memo } from 'react'
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
import ScanningSection from '../components/ScanningSection'
import RecentScansTable from '../components/RecentScansTable'
import InsightsCard from '../components/InsightsCard'
import Modal from '../components/Modal'
import { buildNmapCommand } from '../components/ScanControls'

const Dashboard = () => {
  const { preferences } = useUserPreferences()
  const [recentScans, setRecentScans] = useState([])
  const [systemInfo, setSystemInfo] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isScanning, setIsScanning] = useState(false)
  const [scanningType, setScanningType] = useState(null)
  const [scanProgress, setScanProgress] = useState(null)
  const [scanStatus, setScanStatus] = useState('idle')
  const [scanMessage, setScanMessage] = useState('')
  const [scanId, setScanId] = useState(null)
  const [scanStartTime, setScanStartTime] = useState(null)
  const [selectedScan, setSelectedScan] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const { socket, isConnected, isInitialized } = useSocket()
  const { showToast } = useToast()
  const [pollInterval, setPollInterval] = useState(null)
  const [showScanConfirm, setShowScanConfirm] = useState(false)
  const [pendingScanType, setPendingScanType] = useState(null)
  const [security, setSecurity] = useState({
    vulnScanningEnabled: true,
    osDetectionEnabled: true,
    serviceDetectionEnabled: true,
    aggressiveScanning: false,
  })
  const [networkSettings, setNetworkSettings] = useState({
    defaultTargetNetwork: '172.16.0.0/22'
  })
  const [loadingSettings, setLoadingSettings] = useState(false)
  const [activeTab, setActiveTab] = useState('active')
  const [activeScans, setActiveScans] = useState([])
  const [activeScansLoading, setActiveScansLoading] = useState(false)
  const [stopAllLoading, setStopAllLoading] = useState(false)

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
      if (!scanId || data.scan_id !== scanId) return
      setScanProgress(data.percent)
      setScanStatus(data.status)
      setScanMessage(data.message)
      if (data.status === 'complete' || data.status === 'error') {
        setIsScanning(false)
        setScanningType(null)
        setScanId(null)
        setScanStartTime(null)
        setPollInterval(null)
        loadDashboardData()
        showToast(data.status === 'complete' ? 'Scan completed successfully' : 'Scan failed', data.status === 'complete' ? 'success' : 'danger')
      }
    }

    const handleScanComplete = (data) => {
      if (!scanId || data.scan_id !== scanId) return
      setIsScanning(false)
      setScanningType(null)
      setScanProgress(100)
      setScanStatus('complete')
      setScanMessage('Scan complete!')
      setScanId(null)
      setScanStartTime(null)
      setPollInterval(null)
      loadDashboardData()
      showToast('Scan completed successfully', 'success')
    }

    socket.on('scan_log', handleScanLog)
    socket.on('scan_progress', handleScanProgress)
    socket.on('scan_complete', handleScanComplete)

    return () => {
      socket.off('scan_log', handleScanLog)
      socket.off('scan_progress', handleScanProgress)
      socket.off('scan_complete', handleScanComplete)
    }
  }, [socket, isInitialized, scanId])

  // Poll scan status if no events received
  useEffect(() => {
    if (!scanId) {
      if (pollInterval) clearInterval(pollInterval)
      return
    }
    const interval = setInterval(async () => {
      try {
        const status = await apiService.getScanStatus(scanId)
        setScanProgress(status.percent)
        setScanStatus(status.status)
        setScanMessage(status.message)
        if (status.status === 'complete' || status.status === 'error') {
          setIsScanning(false)
          setScanningType(null)
          setScanId(null)
          setScanStartTime(null)
          clearInterval(interval)
          setPollInterval(null)
          loadDashboardData()
          showToast(status.status === 'complete' ? 'Scan completed successfully' : 'Scan failed', status.status === 'complete' ? 'success' : 'danger')
        }
      } catch (e) {
        // ignore
      }
    }, 3000)
    setPollInterval(interval)
    return () => clearInterval(interval)
  }, [scanId])

  // Fetch active scans
  useEffect(() => {
    if (activeTab !== 'active') return
    let interval = null
    const fetchActive = async () => {
      setActiveScansLoading(true)
      try {
        const resp = await apiService.getActiveScans ? await apiService.getActiveScans() : await fetch('/api/active-scans').then(r => r.json())
        setActiveScans(resp.scans || [])
      } catch {
        setActiveScans([])
      }
      setActiveScansLoading(false)
    }
    fetchActive()
    interval = setInterval(fetchActive, 3000)
    return () => clearInterval(interval)
  }, [activeTab])

  const handleScanTrigger = async (scanType) => {
    try {
      setIsScanning(true)
      setScanningType(scanType)
      setScanProgress(0)
      setScanStatus('running')
      setScanMessage('Starting scan...')
      setScanStartTime(Date.now())
      const resp = await apiService.triggerScan(scanType)
      // Backend does not return scan_id, so fetch latest scan
      const scans = await apiService.getScanHistory()
      const latest = scans.scans && scans.scans.length > 0 ? scans.scans[0] : null
      if (latest) {
        setScanId(latest.id)
      }
      showToast(`${scanType} started`, 'info')
    } catch (error) {
      console.error('Error triggering scan:', error)
      setIsScanning(false)
      setScanningType(null)
      setScanProgress(null)
      setScanStatus('idle')
      setScanMessage('')
      setScanId(null)
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

  const deleteAllScans = async () => {
    if (window.confirm('Are you sure you want to delete ALL scans? This cannot be undone.')) {
      try {
        await apiService.deleteAllScans()
        showToast('All scans deleted successfully', 'success')
        loadDashboardData()
      } catch (error) {
        showToast('Failed to delete all scans', 'danger')
      }
    }
  }

  const testConnection = async () => {
    let httpStatus = 'unknown'
    let socketStatus = 'unknown'
    
    // Test HTTP API
    try {
      const resp = await apiService.ping()
      httpStatus = resp.status === 'success' ? 'HTTP OK' : 'HTTP FAIL'
    } catch {
      httpStatus = 'HTTP FAIL'
    }
    
    // Test Socket.IO
    if (socket && socket.connected) {
      socketStatus = 'Socket.IO OK'
    } else if (socket && !socket.connected) {
      socketStatus = 'Socket.IO FAIL (Disconnected)'
    } else {
      socketStatus = 'Socket.IO FAIL (Not initialized)'
    }
    
    const isSuccess = httpStatus === 'HTTP OK' && socketStatus === 'Socket.IO OK'
    showToast(`API: ${httpStatus}, Socket: ${socketStatus}`, isSuccess ? 'success' : 'danger')
  }

  const handleUploadComplete = (result) => {
    showToast(`Upload successful! Found ${result.hosts_count} hosts and ${result.vulns_count} vulnerabilities.`, 'success')
    loadDashboardData() // Refresh the dashboard to show the new scan
  }

  const handleUploadError = (error) => {
    showToast(error, 'danger')
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

  // Fetch security and network settings for scan confirmation modal
  const fetchScanSettings = async () => {
    setLoadingSettings(true)
    try {
      const data = await apiService.getSettings()
      if (data?.securitySettings) setSecurity(data.securitySettings)
      
      // Get target network from network settings or fallback to scheduled scans target
      const targetNetwork = data?.networkSettings?.defaultTargetNetwork || 
                           data?.scheduledScansSettings?.targetNetwork || 
                           '172.16.0.0/22'
      
      setNetworkSettings({
        ...data?.networkSettings,
        defaultTargetNetwork: targetNetwork
      })
    } catch (error) {
      console.error('Error loading scan settings:', error)
    }
    setLoadingSettings(false)
  }

  const handleRequestScan = async (scanType) => {
    setPendingScanType(scanType)
    setShowScanConfirm(true)
    await fetchScanSettings()
  }

  const handleConfirmScan = () => {
    setShowScanConfirm(false)
    if (pendingScanType) handleScanTrigger(pendingScanType)
    setPendingScanType(null)
  }

  const handleCancelScan = () => {
    setShowScanConfirm(false)
    setPendingScanType(null)
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
    <div className="space-y-6 w-full">
      {/* Header with shimmer/progress bar */}
      <div className="relative">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
      <button
        onClick={clearAllData}
        className="btn btn-error btn-sm flex items-center space-x-2 hover:bg-red-700 hover:text-white transition-colors relative group"
        title="This will wipe all scan history. Are you sure?"
      >
              <Trash2 className="w-6 h-6 text-red-500 group-hover:text-white transition-colors" />
              <span>Clear All Data</span>
            </button>
            <button
              onClick={deleteAllScans}
              className="btn btn-danger btn-sm flex items-center space-x-2 hover:bg-red-800 hover:text-white transition-colors relative group ml-2"
              title="Delete all scans from the database. This cannot be undone."
            >
              <Trash2 className="w-6 h-6 text-red-700 group-hover:text-white transition-colors" />
              <span>Delete All Scans</span>
            </button>
            <button
              onClick={testConnection}
              className="btn btn-info btn-sm flex items-center space-x-2 hover:bg-blue-700 hover:text-white transition-colors relative group ml-2"
              title="Test API and Socket.IO connection"
            >
              <span>Test Connection</span>
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

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Column - Insights and Controls */}
        <div className="lg:col-span-2 space-y-4">
          {/* Insights Card */}
          <InsightsCard />
          
          {/* Scanning Section - Tabbed Interface */}
          <ScanningSection
            onRequestScan={handleRequestScan}
            isScanning={isScanning}
            scanningType={scanningType}
            scanProgress={scanProgress}
            scanStatus={scanStatus}
            scanMessage={scanMessage}
            isConnected={isConnected}
            onUploadComplete={handleUploadComplete}
            onUploadError={handleUploadError}
          />
          
          {/* Tabs for Active/Recent Scans */}
          <div className="mt-6">
            <div className="flex space-x-4 border-b border-gray-700 mb-4">
              <button
                className={`px-4 py-2 font-semibold text-sm transition-colors border-b-2 ${activeTab === 'active' ? 'border-primary-500 text-primary-400' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
                onClick={() => setActiveTab('active')}
              >
                Active Scans
              </button>
              <button
                className={`px-4 py-2 font-semibold text-sm transition-colors border-b-2 ${activeTab === 'recent' ? 'border-primary-500 text-primary-400' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
                onClick={() => setActiveTab('recent')}
              >
                Recent Scans
              </button>
            </div>
            {activeTab === 'active' && (
              <div className="space-y-4">
                <div className="flex justify-end mb-2">
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={stopAllLoading || activeScans.length === 0}
                    onClick={async () => {
                      setStopAllLoading(true)
                      try {
                        const resp = await fetch('/api/kill-all-scans', { method: 'POST' })
                        const data = await resp.json()
                        showToast('All scans stopped', 'success')
                      } catch {
                        showToast('Failed to stop scans', 'danger')
                      }
                      setStopAllLoading(false)
                    }}
                  >
                    {stopAllLoading ? 'Stopping...' : 'Stop All Scans'}
                  </button>
                </div>
                {activeScansLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
                  </div>
                ) : activeScans.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    <p>No active scans at the moment.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {activeScans.map(scan => (
                      <ActiveScanCard
                        key={scan.id}
                        scan={scan}
                        onViewDetails={handleViewDetails}
                        formatTimestamp={formatTimestamp}
                        preferences={preferences}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
            {activeTab === 'recent' && (
              <RecentScansTable
                recentScans={recentScans}
                preferences={preferences}
                handleViewDetails={handleViewDetails}
              />
            )}
          </div>
        </div>

        {/* Right Column - Stats and Recent Scans */}
        <div className="space-y-4">
          {/* System Info Cards Grid */}
          <div className="grid grid-cols-2 gap-3">
            <StatCard
              icon={<Server className="w-6 h-6 text-blue-400 mb-1" />}
              label="Total Scans"
              value={<AnimatedValue value={systemInfo.total_scans || 0} className="text-2xl font-extrabold text-gray-100" />}
              hoverRing="hover:ring-blue-400/40"
            />
            <StatCard
              icon={<Shield className="w-6 h-6 text-green-400 mb-1" />}
              label="Hosts Found"
              value={<AnimatedValue value={systemInfo.hosts_count || 0} className="text-2xl font-extrabold text-gray-100" />}
              hoverRing="hover:ring-green-400/40"
            />
            <StatCard
              icon={VulnIcon({ count: systemInfo.vulns_count })}
              label="Vulnerabilities"
              value={<AnimatedValue value={systemInfo.vulns_count || 0} className={`text-2xl font-extrabold ${systemInfo.vulns_count === 0 ? 'text-green-300' : 'text-red-400'}`} />}
              hoverRing="hover:ring-red-400/40"
            />
            <StatCard
              icon={<Clock className="w-6 h-6 text-yellow-300 mb-1" />}
              label="Last Scan"
              value={<div className="text-lg font-extrabold text-gray-100">{systemInfo.latest_scan_time ? formatTimestamp(systemInfo.latest_scan_time, preferences.use24Hour) : 'Never'}</div>}
              hoverRing="hover:ring-yellow-300/40"
            />
          </div>

          {/* Recent Scans - Compact Version */}
          <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-4">
            <h2 className="text-xl font-title font-bold text-gray-100 mb-4">Recent Scans</h2>
            <div className="space-y-3">
              {recentScans.slice(0, 3).map((scan) => (
                <div key={scan.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                    <div>
                      <div className="text-sm font-medium text-gray-200">{scan.scan_type}</div>
                      <div className="text-xs text-gray-400">{formatTimestamp(scan.timestamp, preferences.use24Hour)}</div>
                    </div>
                  </div>
                  <button 
                    onClick={() => handleViewDetails(scan)}
                    className="text-blue-400 hover:text-blue-300 text-sm"
                    data-testid={`recent-scan-view-btn-${scan.id}`}
                  >
                    View
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Scan Details Modal */}
      <ScanDetailsModal
        scan={selectedScan}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
      {/* Scan Confirmation Modal at root */}
      <Modal
        isOpen={showScanConfirm}
        onClose={handleCancelScan}
        title={pendingScanType ? `Confirm ${pendingScanType}` : 'Confirm Scan'}
        size="md"
      >
        {loadingSettings ? (
          <div className="text-gray-300">Loading scan settings...</div>
        ) : (
          <>
            <div className="mb-4">
              <div className="text-gray-200 mb-2">The following nmap command will be used:</div>
              <div className="text-xs text-gray-400 mb-1">Target Network: {networkSettings.defaultTargetNetwork}</div>
              <pre className="bg-gray-900 text-green-400 rounded p-3 text-sm overflow-x-auto whitespace-pre-wrap">
                {pendingScanType ? buildNmapCommand(pendingScanType, security, networkSettings.defaultTargetNetwork) : 'Loading scan configuration...'}
              </pre>
            </div>
            <div className="flex justify-end space-x-3">
              <button
                className="btn btn-ghost"
                onClick={handleCancelScan}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleConfirmScan}
              >
                Start Scan
              </button>
            </div>
          </>
        )}
      </Modal>
    </div>
  )
}

const ActiveScanCard = memo(function ActiveScanCard({ scan, onViewDetails, formatTimestamp, preferences }) {
  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-6 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-2">
        <div className="text-lg font-title font-bold text-gray-100">{scan.scan_type}</div>
        <div className="text-xs text-gray-400">ID: {scan.id}</div>
      </div>
      <div className="mb-2 text-sm text-gray-300">Started: {scan.timestamp ? formatTimestamp(scan.timestamp, preferences.use24Hour) : '-'}</div>
      <div className="mb-2 text-sm text-gray-300">Status: <span className="font-semibold text-primary-400">{scan.status}</span></div>
      <div className="mb-2 text-sm text-gray-300">Progress: <span className="font-semibold">{scan.percent ? `${Math.round(scan.percent)}%` : '0%'}</span></div>
      <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden mb-2">
        <div
          className="bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 h-2 rounded-full animate-pulse transition-all duration-300"
          style={{ width: `${scan.percent || 0}%`, transition: 'width 0.5s cubic-bezier(0.4,0,0.2,1)' }}
        ></div>
      </div>
      <button
        className="btn btn-outline btn-sm mt-2 w-full"
        onClick={() => onViewDetails(scan)}
      >
        View Details
      </button>
    </div>
  )
})

export default Dashboard 