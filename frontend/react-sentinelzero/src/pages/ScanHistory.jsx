import React, { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import ScanDetailsModal from '../components/ScanDetailsModal'
import { Info, Eye, History, RefreshCw, AlertCircle } from 'lucide-react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'
import { formatTimestamp } from '../utils/date'
import ScanHistoryTable from '../components/ScanHistoryTable'
import Button from '../components/Button'

const ScanHistory = () => {
  const { preferences } = useUserPreferences()
  const [scans, setScans] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedScan, setSelectedScan] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncStatus, setSyncStatus] = useState(null)
  const { showToast } = useToast()

  const loadScanHistory = async () => {
    try {
      const data = await apiService.getScanHistory()
      setScans(data.scans || [])
      setIsLoading(false)
    } catch (error) {
      console.error('Error loading scan history:', error)
      setError('Failed to load scan history')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadScanHistory()
    loadSyncStatus()
  }, [])

  const loadSyncStatus = async () => {
    try {
      const data = await apiService.getSyncStatus()
      setSyncStatus(data.sync_status)
    } catch (error) {
      console.error('Error loading sync status:', error)
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

  const handleClearScan = async (scanId) => {
    if (window.confirm('Are you sure you want to delete this scan?')) {
      try {
        await apiService.clearScan(scanId)
        showToast('Scan deleted successfully', 'success')
        loadScanHistory()
      } catch (error) {
        console.error('Error deleting scan:', error)
        showToast('Failed to delete scan', 'danger')
      }
    }
  }

  const handleSyncScans = async () => {
    setIsSyncing(true)
    try {
      const result = await apiService.syncScans()
      showToast(result.message, 'success')
      loadScanHistory()
      loadSyncStatus()
    } catch (error) {
      console.error('Error syncing scans:', error)
      showToast('Failed to sync scans', 'danger')
    } finally {
      setIsSyncing(false)
    }
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
        <History className="mx-auto h-12 w-12 text-red-500" />
        <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">Error</h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-10 w-full">
      {/* Sync Status and Controls */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <History className="h-6 w-6 text-primary-500" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Scan History</h2>
          </div>
          <div className="flex items-center space-x-3">
            {syncStatus && !syncStatus.in_sync && (
              <div className="flex items-center space-x-2 text-amber-600 dark:text-amber-400">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">
                  {syncStatus.missing_in_database} scans not synced
                </span>
              </div>
            )}
            <Button
              onClick={handleSyncScans}
              disabled={isSyncing}
              variant="primary"
              size="sm"
              className="flex items-center space-x-2"
            >
              <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
              <span>{isSyncing ? 'Syncing...' : 'Sync Scans'}</span>
            </Button>
          </div>
        </div>
        
        {syncStatus && (
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Database: {syncStatus.database_scans} scans | 
            Filesystem: {syncStatus.filesystem_files} files | 
            Status: {syncStatus.in_sync ? 'In sync' : 'Out of sync'}
          </div>
        )}
      </div>

      <ScanHistoryTable
        scans={scans}
        preferences={preferences}
        handleViewDetails={handleViewDetails}
      />
      <ScanDetailsModal
        scan={selectedScan}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  )
}

export default ScanHistory 