import React from 'react'
import { Info, Eye } from 'lucide-react'
import { formatTimestamp } from '../utils/date'

const RecentScansTable = ({ recentScans, preferences, handleViewDetails }) => (
  <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-6">
    <h2 className="text-2xl font-title font-bold text-gray-100 mb-4">Recent Scans</h2>
    {/* Desktop Table */}
    <div className="hidden md:block overflow-x-auto">
      <table className="table w-full">
        <thead className="bg-gray-900/80">
          <tr>
            <th className="font-bold text-gray-200">TIMESTAMP</th>
            <th className="font-bold text-gray-200">TYPE</th>
            <th className="font-bold text-gray-200">HOSTS</th>
            <th className="font-bold text-gray-200">VULNS</th>
            <th className="font-bold text-gray-200">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {recentScans.map((scan) => (
            <tr key={scan.id} className="hover:bg-gray-800/60 transition-colors group" data-testid={`recent-scan-row-${scan.id}`}>
              <td>{formatTimestamp(scan.timestamp, preferences.use24Hour)}</td>
              <td>
                <span className="inline-flex items-center gap-1 badge badge-primary bg-blue-700/20 text-blue-200 px-2 py-1 rounded-md">
                  <Info className="w-4 h-4 text-blue-400" />
                  {scan.scan_type}
                </span>
              </td>
              <td>{scan.hosts_count || 0}</td>
              <td>{scan.vulns_count || 0}</td>
              <td>
                <button className="btn btn-outline btn-sm group-hover:shadow-blue-400/40 group-hover:shadow-lg transition-all" onClick={() => handleViewDetails(scan)} data-testid={`recent-scan-view-btn-${scan.id}`}>
                  <Eye className="w-3 h-3" /> View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    {/* Mobile Cards */}
    <div className="md:hidden space-y-4">
      {recentScans.map((scan) => (
        <div key={scan.id} className="bg-white/10 dark:bg-gray-900/30 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-4 space-y-3" data-testid={`recent-scan-card-${scan.id}`}>
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="text-sm text-gray-400">
                {formatTimestamp(scan.timestamp, preferences.use24Hour)}
              </div>
              <div className="mt-1">
                <span className="inline-flex items-center gap-1 badge badge-primary bg-blue-700/20 text-blue-200 px-2 py-1 rounded-md">
                  <Info className="w-4 h-4 text-blue-400" />
                  {scan.scan_type}
                </span>
              </div>
            </div>
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
            <button className="btn btn-outline btn-sm w-full hover:shadow-blue-400/40 hover:shadow-lg transition-all" onClick={() => handleViewDetails(scan)} data-testid={`recent-scan-view-btn-mobile-${scan.id}`}>
              <Eye className="w-3 h-3" /> View
            </button>
          </div>
        </div>
      ))}
    </div>
  </div>
)

export default RecentScansTable 