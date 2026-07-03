import React, { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import ScanDetailsModal from '../components/ScanDetailsModal'
import { AlertCircle } from 'lucide-react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'
import ScanHistoryTable from '../components/ScanHistoryTable'

const ScanHistory = () => {
  const { preferences } = useUserPreferences()
  const [scans, setScans] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedScan, setSelectedScan] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncMode, setSyncMode] = useState('import_missing')
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
      const result = await apiService.syncScans(syncMode)
      const sr = result.sync_result || {}
      const parts = []
      if (sr.synced_count) parts.push(`imported ${sr.synced_count}`)
      if (sr.skipped_count) parts.push(`${sr.skipped_count} already indexed`)
      if (sr.skipped_artifacts) parts.push(`skipped ${sr.skipped_artifacts} pre-discovery artifacts`)
      if (sr.pruned_count) parts.push(`pruned ${sr.pruned_count} stale records`)
      if (sr.error_count) parts.push(`${sr.error_count} errors`)
      const detail = parts.length ? parts.join(', ') : 'no changes'
      showToast(result.message ? `${result.message}: ${detail}` : `Sync complete: ${detail}`, 'success')
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
    <div className="space-y-4 w-full">
      {syncStatus && !syncStatus.in_sync && (
        <div className="flex items-center gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 dark:text-amber-300 dark:bg-amber-900/20 dark:border-amber-700/40 rounded-md px-4 py-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{syncStatus.missing_in_database} scan file{syncStatus.missing_in_database !== 1 ? 's' : ''} not indexed in database</span>
        </div>
      )}

      <ScanHistoryTable
        scans={scans}
        preferences={preferences}
        handleViewDetails={handleViewDetails}
        onSync={handleSyncScans}
        isSyncing={isSyncing}
        syncMode={syncMode}
        onSyncModeChange={setSyncMode}
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
