import React, { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import ScanDetailsModal from '../components/ScanDetailsModal'
import { Info, Eye, History } from 'lucide-react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'
import { formatTimestamp } from '../utils/date'
import ScanHistoryTable from '../components/ScanHistoryTable'

const ScanHistory = () => {
  const { preferences } = useUserPreferences()
  const [scans, setScans] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedScan, setSelectedScan] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [filterType, setFilterType] = useState('all')
  const [searchTerm, setSearchTerm] = useState('')
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
  }, [])

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

  const filteredScans = scans.filter(scan => {
    const matchesType = filterType === 'all' || scan.scan_type === filterType
    const matchesSearch = searchTerm === '' || 
      scan.scan_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      scan.id.toString().includes(searchTerm)
    return matchesType && matchesSearch
  })

  const scanTypes = [...new Set(scans.map(scan => scan.scan_type))]

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