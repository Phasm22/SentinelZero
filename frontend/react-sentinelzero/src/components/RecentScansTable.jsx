import React from 'react'
import { Info, Eye } from 'lucide-react'
import { formatTimestamp } from '../utils/date'
import Button from './Button'

const RecentScansTable = ({ recentScans, preferences, handleViewDetails }) => (
  <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-6" data-testid="recent-scans-table">
    <h2 className="text-2xl font-title font-bold text-gray-100 mb-4" data-testid="recent-scans-title">Recent Scans</h2>
    {/* Desktop Table */}
    <div className="hidden md:block overflow-x-auto" data-testid="desktop-table">
      <table className="table w-full" data-testid="scans-table">
        <thead className="bg-gray-900/80" data-testid="table-header">
          <tr>
            <th className="font-bold text-gray-200" data-testid="timestamp-header">TIMESTAMP</th>
            <th className="font-bold text-gray-200" data-testid="type-header">TYPE</th>
            <th className="font-bold text-gray-200" data-testid="hosts-header">HOSTS</th>
            <th className="font-bold text-gray-200" data-testid="vulns-header">VULNS</th>
            <th className="font-bold text-gray-200" data-testid="actions-header">ACTIONS</th>
          </tr>
        </thead>
        <tbody data-testid="table-body">
          {recentScans.map((scan) => (
            <tr key={scan.id} className="hover:bg-gray-800/60 transition-colors group" data-testid={`recent-scan-row-${scan.id}`}>
              <td data-testid="scan-timestamp">{formatTimestamp(scan.timestamp, preferences.use24Hour)}</td>
              <td data-testid="scan-type-cell">
                <span className="inline-flex items-center gap-1 badge badge-primary bg-blue-600/30 text-blue-100 border border-blue-500/30 px-2 py-1 rounded-md font-medium">
                  <Info className="w-4 h-4 text-blue-300" />
                  {scan.scan_type}
                </span>
              </td>
              <td data-testid="scan-hosts-count">{scan.hosts_count || 0}</td>
              <td data-testid="scan-vulns-count">{scan.vulns_count || 0}</td>
              <td data-testid="scan-actions">
                <Button 
                  variant="outline" 
                  size="sm" 
                  icon={<Eye className="w-3 h-3" />}
                  onClick={() => handleViewDetails(scan)} 
                  data-testid={`recent-scan-view-btn-${scan.id}`}
                >
                  View
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    {/* Mobile Cards */}
    <div className="md:hidden space-y-4" data-testid="mobile-cards">
      {recentScans.map((scan) => (
        <div key={scan.id} className="bg-white/10 dark:bg-gray-900/30 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-4 space-y-3" data-testid={`recent-scan-card-${scan.id}`}>
          <div className="flex items-center justify-between" data-testid="card-header">
            <div className="flex-1">
              <div className="text-sm text-gray-400" data-testid="card-timestamp">
                {formatTimestamp(scan.timestamp, preferences.use24Hour)}
              </div>
              <div className="mt-1">
                <span className="inline-flex items-center gap-1 badge badge-primary bg-blue-600/30 text-blue-100 border border-blue-500/30 px-2 py-1 rounded-md font-medium" data-testid="card-scan-type">
                  <Info className="w-4 h-4 text-blue-300" />
                  {scan.scan_type}
                </span>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm" data-testid="card-stats">
            <div data-testid="hosts-stat">
              <div className="text-gray-400 font-medium">Hosts</div>
              <div className="text-gray-100 font-semibold" data-testid="hosts-count">
                {scan.hosts_count || 0}
              </div>
            </div>
            <div data-testid="vulns-stat">
              <div className="text-gray-400 font-medium">Vulnerabilities</div>
              <div className="text-gray-100 font-semibold" data-testid="vulns-count">
                {scan.vulns_count || 0}
              </div>
            </div>
          </div>
          <div className="pt-2" data-testid="card-actions">
            <Button 
              variant="outline" 
              size="sm" 
              icon={<Eye className="w-3 h-3" />}
              className="w-full"
              onClick={() => handleViewDetails(scan)} 
              data-testid={`recent-scan-view-btn-mobile-${scan.id}`}
            >
              View
            </Button>
          </div>
        </div>
      ))}
    </div>
  </div>
)

export default RecentScansTable 