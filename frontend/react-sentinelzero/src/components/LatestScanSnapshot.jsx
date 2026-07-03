import React from 'react'
import { Server, Shield, Clock, Bug } from 'lucide-react'
import AnimatedValue from '@/components/AnimatedValue'
import Button from '@/components/Button'

const MetricTile = ({ icon, label, value, testId }) => (
  <div
    className="rounded-lg border border-white/10 bg-white/5 p-3 sm:p-4 flex flex-col items-center justify-center gap-2 text-center min-h-[5.5rem]"
    data-testid={testId}
  >
    <div className="flex items-center justify-center gap-2 text-[11px] uppercase tracking-wide text-gray-400">
      {icon}
      <span>{label}</span>
    </div>
    <div>{value}</div>
  </div>
)

const LatestScanSnapshot = ({
  scan,
  totalScans = 0,
  preferences,
  onViewDetails,
  formatTimestamp,
}) => {
  if (!scan) {
    return (
      <div
        className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 rounded-md shadow-xl p-4 sm:p-5"
        data-testid="latest-scan-snapshot"
      >
        <h2 className="text-lg font-title font-bold text-gray-100">Latest Scan</h2>
        <p className="mt-2 text-sm text-gray-400">No scans yet — run one to see hosts and vulnerabilities here.</p>
        {totalScans > 0 && (
          <p className="mt-3 text-sm text-gray-400 flex items-center gap-1.5" data-testid="total-scans-stat">
            <Server className="w-3.5 h-3.5 flex-shrink-0" />
            {totalScans} scan{totalScans === 1 ? '' : 's'} all-time
          </p>
        )}
      </div>
    )
  }

  const vulnCount = scan.vulns_count || 0
  const vulnValueClass = vulnCount > 0
    ? 'text-xl sm:text-2xl font-extrabold font-mono text-red-400'
    : 'text-xl sm:text-2xl font-extrabold font-mono text-gray-100'

  return (
    <div
      className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 rounded-md shadow-xl p-4 sm:p-5"
      data-testid="latest-scan-snapshot"
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg sm:text-xl font-title font-bold text-gray-100">Latest Scan</h2>
          <div
            className="mt-1 flex items-center gap-1.5 text-sm text-gray-400 min-w-0"
            data-testid="latest-scan-time"
          >
            <Clock className="w-3.5 h-3.5 flex-shrink-0" />
            <time className="whitespace-nowrap tabular-nums">
              {formatTimestamp(scan.timestamp, preferences.use24Hour)}
            </time>
          </div>
          {scan.scan_type && (
            <span className="mt-2 inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-xs text-blue-200">
              {scan.scan_type}
            </span>
          )}
        </div>
        <Button
          onClick={() => onViewDetails(scan)}
          variant="outline"
          size="sm"
          className="flex-shrink-0 text-xs sm:text-sm"
          data-testid="latest-scan-view-btn"
        >
          View
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:gap-3">
        <MetricTile
          icon={<Shield className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />}
          label="Hosts found"
          value={
            <AnimatedValue
              value={scan.hosts_count || 0}
              className="text-xl sm:text-2xl font-extrabold font-mono text-gray-100"
            />
          }
          testId="hosts-found-stat"
        />
        <MetricTile
          icon={(
            <Bug
              className={`w-3.5 h-3.5 flex-shrink-0 ${vulnCount > 0 ? 'text-red-400' : 'text-amber-400/90'}`}
            />
          )}
          label="Vulnerabilities"
          value={(
            <AnimatedValue
              value={vulnCount}
              className={vulnValueClass}
            />
          )}
          testId="vulnerabilities-stat"
        />
      </div>

      <p className="mt-3 pt-3 border-t border-white/10 text-sm text-gray-400 flex items-center gap-1.5" data-testid="total-scans-stat">
        <Server className="w-3.5 h-3.5 flex-shrink-0" />
        {totalScans} scan{totalScans === 1 ? '' : 's'} all-time
      </p>
    </div>
  )
}

export default LatestScanSnapshot
