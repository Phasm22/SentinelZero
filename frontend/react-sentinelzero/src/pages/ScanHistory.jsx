import React, { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import ScanDetailsModal from '../components/ScanDetailsModal'
import { 
  History, 
  Trash2, 
  Eye,
  Filter,
  Search
} from 'lucide-react'

const ScanHistory = () => {
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Scan History</h1>
          <p className="text-gray-600 dark:text-gray-400">View and manage all network scans</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search scans..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 w-full border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Filter by Type
            </label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value="all">All Types</option>
              {scanTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Scans List */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Scans ({filteredScans.length})
          </h2>
        </div>
        <div className="p-6">
          {filteredScans.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <History className="mx-auto h-12 w-12 mb-4" />
              <p>No scans found.</p>
            </div>
          ) : (
            <>
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto">
                <table className="table w-full">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Timestamp</th>
                      <th>Type</th>
                      <th>Hosts</th>
                      <th>Vulns</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredScans.map((scan) => (
                      <tr key={scan.id}>
                        <td className="font-mono">#{scan.id}</td>
                        <td>{formatTimestamp(scan.timestamp)}</td>
                        <td>
                          <span className="badge badge-primary">
                            {scan.scan_type}
                          </span>
                        </td>
                        <td>{scan.hosts_count || 0}</td>
                        <td>{scan.vulns_count || 0}</td>
                        <td>
                          <div className="flex items-center space-x-2">
                            <button 
                              className="btn btn-outline btn-sm flex items-center space-x-1"
                              onClick={() => handleViewDetails(scan)}
                            >
                              <Eye className="w-3 h-3" />
                              <span>View</span>
                            </button>
                            <button 
                              className="btn btn-outline btn-sm btn-error flex items-center space-x-1"
                              onClick={() => handleClearScan(scan.id)}
                            >
                              <Trash2 className="w-3 h-3" />
                              <span>Delete</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Cards */}
              <div className="md:hidden space-y-4">
                {filteredScans.map((scan) => (
                  <div key={scan.id} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2 mb-1">
                          <span className="text-sm font-mono text-gray-500 dark:text-gray-400">
                            #{scan.id}
                          </span>
                          <span className="badge badge-primary">
                            {scan.scan_type}
                          </span>
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {formatTimestamp(scan.timestamp)}
                        </div>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <div className="text-gray-500 dark:text-gray-400 font-medium">Hosts</div>
                        <div className="text-gray-900 dark:text-white font-semibold">
                          {scan.hosts_count || 0}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500 dark:text-gray-400 font-medium">Vulnerabilities</div>
                        <div className="text-gray-900 dark:text-white font-semibold">
                          {scan.vulns_count || 0}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex space-x-2 pt-2">
                      <button 
                        className="btn btn-outline btn-sm flex-1 flex items-center justify-center space-x-1"
                        onClick={() => handleViewDetails(scan)}
                      >
                        <Eye className="w-3 h-3" />
                        <span>View Details</span>
                      </button>
                      <button 
                        className="btn btn-outline btn-sm btn-error flex items-center justify-center space-x-1"
                        onClick={() => handleClearScan(scan.id)}
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>Delete</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Scan Details Modal */}
      <ScanDetailsModal
        scan={selectedScan}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  )
}

export default ScanHistory 