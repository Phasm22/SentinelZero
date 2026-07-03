import React from 'react'
import Button from './Button'
import { formatTimestamp } from '../utils/date'

const RecentScansList = ({
  scans,
  preferences,
  onViewDetails,
  isViewed,
  limit = 3,
}) => {
  const items = scans.slice(0, limit)

  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400" data-testid="no-recent-scans">
        <p>No recent scans yet.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2 sm:space-y-3" data-testid="recent-scans-list">
      {items.map((scan) => (
        <div
          key={scan.id}
          className="flex items-center justify-between p-2 sm:p-3 bg-white/5 dark:bg-white/5 rounded-md border border-gray-200/50 dark:border-transparent"
          data-testid={`recent-scan-item-${scan.id}`}
        >
          <div className="flex items-center space-x-2 sm:space-x-3 min-w-0 flex-1">
            {!isViewed(scan.id) && (
              <div
                className="w-2 h-2 bg-blue-400 rounded-full flex-shrink-0"
                data-testid="scan-status-indicator"
                aria-hidden="true"
              />
            )}
            <div className="min-w-0 flex-1">
              <div
                className="text-xs sm:text-sm font-medium text-gray-900 dark:text-gray-200 truncate"
                data-testid="scan-type"
              >
                {scan.scan_type}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 truncate" data-testid="scan-timestamp">
                {formatTimestamp(scan.timestamp, preferences.use24Hour)}
              </div>
            </div>
          </div>
          <Button
            onClick={() => onViewDetails(scan)}
            variant="outline"
            size="sm"
            className="text-xs sm:text-sm flex-shrink-0"
            data-testid={`recent-scan-view-btn-${scan.id}`}
          >
            View
          </Button>
        </div>
      ))}
    </div>
  )
}

export default RecentScansList
