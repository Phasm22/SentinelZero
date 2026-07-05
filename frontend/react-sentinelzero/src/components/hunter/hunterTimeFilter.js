export const TIME_RANGE_OPTIONS = [
  { value: '24h', label: 'Past 24h', days: 1 },
  { value: '7d', label: 'Past 7d', days: 7 },
  { value: '30d', label: 'Past 30d', days: 30 },
  { value: 'all', label: 'All time', days: null },
]

export function getTimeRangeCutoff(timeRange) {
  const option = TIME_RANGE_OPTIONS.find((item) => item.value === timeRange)
  if (!option?.days) return null
  return Date.now() - option.days * 24 * 60 * 60 * 1000
}

export function isWithinTimeRange(timestamp, timeRange) {
  const cutoff = getTimeRangeCutoff(timeRange)
  if (!cutoff) return true
  const value = Date.parse(timestamp || '')
  if (Number.isNaN(value)) return false
  return value >= cutoff
}

export function filterRunsByTimeRange(runs, timeRange) {
  return (runs || []).filter((run) => isWithinTimeRange(run?.huntRun?.completedAt, timeRange))
}

export function filterMissionsByTimeRange(missions, timeRange) {
  return (missions || []).filter((mission) => {
    const timestamp = mission?.updatedAt || mission?.startedAt
    return isWithinTimeRange(timestamp, timeRange)
  })
}

export function runTimeLabel(meta = {}) {
  if (meta.completedAt) {
    const value = Date.parse(meta.completedAt)
    if (!Number.isNaN(value)) {
      const diffMs = Date.now() - value
      const diffMins = Math.floor(diffMs / 60000)
      if (diffMins < 1) return 'just now'
      if (diffMins < 60) return `${diffMins}m ago`
      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}h ago`
      const diffDays = Math.floor(diffHours / 24)
      return `${diffDays}d ago`
    }
  }
  if (meta.missionType === 'pivot') return 'in progress'
  return '—'
}
