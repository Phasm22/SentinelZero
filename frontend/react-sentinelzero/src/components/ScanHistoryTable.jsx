import React from 'react'
import { Info, Eye } from 'lucide-react'
import { formatTimestamp } from '../utils/date'

const ScanHistoryTable = ({ scans, preferences, handleViewDetails }) => (
  <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-2xl p-8 flex flex-col gap-4">
    <div className="flex items-center mb-4">
      <Info className="w-7 h-7 text-blue-400 mr-3" />
      <h3 className="text-2xl font-title font-bold text-gray-100">All Scans</h3>
    </div>
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
          {scans.map((scan) => (
            <tr key={scan.id} className="hover:bg-gray-800/60 transition-colors group">
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
                <button className="btn btn-outline btn-sm group-hover:shadow-blue-400/40 group-hover:shadow-lg transition-all" onClick={() => handleViewDetails(scan)}>
                  <Eye className="w-3 h-3" /> View Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    {/* Mobile Cards */}
    <div className="md:hidden space-y-4">
      {scans.map((scan) => (
        <div key={scan.id} className="bg-white/10 dark:bg-gray-900/30 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-4 space-y-3">
          <div className="flex items-center mb-2">
            <Info className="w-5 h-5 text-blue-400 mr-2" />
            <span className="badge badge-primary bg-blue-700/20 text-blue-200 px-2 py-1 rounded-md">
              {scan.scan_type}
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
            <button className="btn btn-outline btn-sm w-full hover:shadow-blue-400/40 hover:shadow-lg transition-all" onClick={() => handleViewDetails(scan)}>
              <Eye className="w-3 h-3" /> View Details
            </button>
          </div>
        </div>
      ))}
    </div>
  </div>
)

export default ScanHistoryTable 