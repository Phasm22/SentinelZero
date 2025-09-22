import React, { useState, useMemo } from 'react'
import { Info, Eye, ChevronUp, ChevronDown, ChevronsUpDown, Search, Filter } from 'lucide-react'
import { formatTimestamp } from '../utils/date'
import Button from './Button'

const ScanHistoryTable = ({ scans, preferences, handleViewDetails }) => {
  const [sortField, setSortField] = useState('timestamp')
  const [sortDirection, setSortDirection] = useState('desc')
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const sortableFields = {
    timestamp: { label: 'TIMESTAMP', type: 'date' },
    scan_type: { label: 'TYPE', type: 'string' },
    hosts_count: { label: 'HOSTS', type: 'number' },
    vulns_count: { label: 'VULNS', type: 'number' },
    status: { label: 'STATUS', type: 'string' }
  }

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const filteredAndSortedScans = useMemo(() => {
    let filtered = scans.filter(scan => {
      // Search filter
      const matchesSearch = searchTerm === '' || 
        scan.scan_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
        scan.id.toString().includes(searchTerm) ||
        (scan.status && scan.status.toLowerCase().includes(searchTerm.toLowerCase()))
      
      // Status filter
      const matchesStatus = statusFilter === 'all' || scan.status === statusFilter
      
      return matchesSearch && matchesStatus
    })

    // Sort the filtered results
    return filtered.sort((a, b) => {
      let aValue = a[sortField]
      let bValue = b[sortField]

      // Handle different data types
      if (sortField === 'timestamp') {
        aValue = new Date(aValue)
        bValue = new Date(bValue)
      } else if (sortableFields[sortField].type === 'number') {
        aValue = Number(aValue) || 0
        bValue = Number(bValue) || 0
      } else {
        aValue = String(aValue || '').toLowerCase()
        bValue = String(bValue || '').toLowerCase()
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1
      return 0
    })
  }, [scans, sortField, sortDirection, searchTerm, statusFilter])

  const getSortIcon = (field) => {
    if (sortField !== field) {
      return <ChevronsUpDown className="w-4 h-4 text-gray-400" />
    }
    return sortDirection === 'asc' 
      ? <ChevronUp className="w-4 h-4 text-blue-400" />
      : <ChevronDown className="w-4 h-4 text-blue-400" />
  }

  // Get unique statuses for filter dropdown
  const uniqueStatuses = useMemo(() => {
    const statuses = [...new Set(scans.map(scan => scan.status).filter(Boolean))]
    return statuses.sort()
  }, [scans])

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-2xl p-8 flex flex-col gap-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <Info className="w-7 h-7 text-blue-400 mr-3" />
          <h3 className="text-2xl font-title font-bold text-gray-100">All Scans</h3>
          <span className="ml-3 px-2 py-1 bg-blue-600/30 text-blue-100 text-sm rounded-full">
            {filteredAndSortedScans.length} of {scans.length}
          </span>
        </div>
      </div>

      {/* Search and Filter Controls */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search scans by type, ID, or status..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-900/50 border border-gray-600 rounded-md text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="pl-10 pr-8 py-2 bg-gray-900/50 border border-gray-600 rounded-md text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none"
          >
            <option value="all">All Statuses</option>
            {uniqueStatuses.map(status => (
              <option key={status} value={status} className="capitalize">
                {status}
              </option>
            ))}
          </select>
        </div>
      </div>
      {/* Desktop Table */}
      <div className="hidden md:block overflow-x-auto">
        {filteredAndSortedScans.length === 0 ? (
          <div className="text-center py-12">
            <Search className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-200 mb-2">No scans found</h3>
            <p className="text-gray-400">
              {searchTerm || statusFilter !== 'all' 
                ? 'Try adjusting your search or filter criteria'
                : 'No scans available'
              }
            </p>
          </div>
        ) : (
          <table className="table w-full">
            <thead className="bg-gray-900/80">
              <tr>
                {Object.entries(sortableFields).map(([field, config]) => (
                  <th 
                    key={field}
                    className="font-bold text-gray-200 cursor-pointer hover:bg-gray-800/60 transition-colors select-none"
                    onClick={() => handleSort(field)}
                  >
                    <div className="flex items-center gap-2">
                      <span>{config.label}</span>
                      {getSortIcon(field)}
                    </div>
                  </th>
                ))}
                <th className="font-bold text-gray-200">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedScans.map((scan) => (
                <tr key={scan.id} className="hover:bg-gray-800/60 transition-colors group" data-testid={`history-scan-row-${scan.id}`}>
                  <td>{formatTimestamp(scan.timestamp, preferences.use24Hour)}</td>
                  <td>
                    <span className="inline-flex items-center gap-1 badge badge-primary bg-blue-600/30 text-blue-100 border border-blue-500/30 px-2 py-1 rounded-md font-medium">
                      <Info className="w-4 h-4 text-blue-300" />
                      {scan.scan_type}
                    </span>
                  </td>
                  <td>{scan.hosts_count || 0}</td>
                  <td>{scan.vulns_count || 0}</td>
                  <td>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                      scan.status === 'complete' 
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                        : scan.status === 'running' || scan.status === 'parsing' || scan.status === 'saving'
                        ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                        : scan.status === 'error'
                        ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400'
                    }`}>
                      {scan.status || 'unknown'}
                    </span>
                  </td>
                  <td>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      icon={<Eye className="w-3 h-3" />}
                      onClick={() => handleViewDetails(scan)} 
                      data-testid={`history-scan-view-btn-${scan.id}`}
                    >
                      View Details
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {/* Mobile Cards */}
      <div className="md:hidden space-y-4">
        {filteredAndSortedScans.length === 0 ? (
          <div className="text-center py-12">
            <Search className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-200 mb-2">No scans found</h3>
            <p className="text-gray-400">
              {searchTerm || statusFilter !== 'all' 
                ? 'Try adjusting your search or filter criteria'
                : 'No scans available'
              }
            </p>
          </div>
        ) : (
          filteredAndSortedScans.map((scan) => (
          <div key={scan.id} className="bg-white/10 dark:bg-gray-900/30 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-4 space-y-3" data-testid={`history-scan-card-${scan.id}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center">
                <Info className="w-5 h-5 text-blue-400 mr-2" />
                <span className="badge badge-primary bg-blue-600/30 text-blue-100 border border-blue-500/30 px-2 py-1 rounded-md font-medium">
                  {scan.scan_type}
                </span>
              </div>
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                scan.status === 'complete' 
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                  : scan.status === 'running' || scan.status === 'parsing' || scan.status === 'saving'
                  ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                  : scan.status === 'error'
                  ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                  : 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400'
              }`}>
                {scan.status || 'unknown'}
              </span>
            </div>
            <div className="text-sm text-gray-400 mb-1">
              {formatTimestamp(scan.timestamp, preferences.use24Hour)}
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-400 font-medium">Hosts</div>
                <div className="text-gray-100 font-semibold">
                  {scan.hosts_count || 0}
                </div>
              </div>
              <div>
                <div className="text-gray-400 font-medium">Vulnerabilities</div>
                <div className="text-gray-100 font-semibold">
                  {scan.vulns_count || 0}
                </div>
              </div>
            </div>
            <div className="pt-2">
              <Button 
                variant="outline" 
                size="sm" 
                icon={<Eye className="w-3 h-3" />}
                className="w-full"
                onClick={() => handleViewDetails(scan)} 
                data-testid={`history-scan-view-btn-mobile-${scan.id}`}
              >
                View Details
              </Button>
            </div>
          </div>
          ))
        )}
      </div>
    </div>
  )
}

export default ScanHistoryTable 