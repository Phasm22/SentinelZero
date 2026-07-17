import axios from 'axios'

const API_BASE_URL = '/api'

export const apiService = {
  // Scan operations
  triggerScan: async (scanType) => {
    const response = await axios.post(`${API_BASE_URL}/scan`, 
      `scan_type=${encodeURIComponent(scanType)}`,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    )
    return response.data
  },

  getScanHistory: async () => {
    const response = await axios.get(`${API_BASE_URL}/scan-history`)
    return response.data
  },

  getScanHosts: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/hosts/${scanId}`)
    return response.data
  },

  getScanVulns: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/vulns/${scanId}`)
    return response.data
  },

  getScanXml: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/scan-xml/${scanId}`, {
      responseType: 'text',
    })
    return response.data
  },

  getScanStatus: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/scan-status/${scanId}`)
    return response.data
  },

  getActiveScans: async () => {
    const response = await axios.get(`${API_BASE_URL}/active-scans`)
    return response.data
  },

  getScan: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/scan/${scanId}`)
    return response.data
  },

  clearScan: async (scanId) => {
    const response = await axios.post(`/clear-scan/${scanId}`)
    return response.data
  },

  clearAllData: async () => {
    const response = await axios.post(`${API_BASE_URL}/data/delete`, {
      scope: 'all',
      delete_files: true,
      prune_orphan_files: true,
      sync_after: false,
    })
    return response.data
  },

  deleteAllScans: async (options = {}) => {
    const response = await axios.post(`${API_BASE_URL}/delete-all-scans`, {
      delete_files: Boolean(options.deleteFiles),
      prune_orphan_files: Boolean(options.pruneOrphanFiles),
    })
    return response.data
  },

  uploadScan: async (formData) => {
    const response = await axios.post(`${API_BASE_URL}/upload-scan`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // Dashboard stats
  getDashboardStats: async () => {
    const response = await axios.get(`${API_BASE_URL}/dashboard-stats`)
    return response.data
  },

  // Schedule operations
  getSchedule: async () => {
    const response = await axios.get(`${API_BASE_URL}/schedule`)
    return response.data
  },

  updateSchedule: async (schedule) => {
    const response = await axios.post(`${API_BASE_URL}/schedule`, schedule)
    return response.data
  },

  getSchedules: async () => {
    const response = await axios.get(`${API_BASE_URL}/schedules`)
    return response.data
  },

  deleteSchedule: async (jobId) => {
    const response = await axios.delete(`${API_BASE_URL}/schedules/${jobId}`)
    return response.data
  },

  // Settings
  getSettings: async () => {
    const response = await axios.get(`${API_BASE_URL}/settings`)
    return response.data
  },

  updateSettings: async (settings) => {
    const response = await axios.post(`${API_BASE_URL}/settings`, settings)
    return response.data
  },

  getNetworkInterfaces: async () => {
    const response = await axios.get(`${API_BASE_URL}/network-interfaces`)
    return response.data
  },

  testPushoverConnection: async () => {
    const response = await axios.post(`${API_BASE_URL}/test-pushover`)
    return response.data
  },

  updateSetting: async (section, key, value) => {
    const response = await axios.post(`${API_BASE_URL}/settings`, {
      section,
      key,
      value,
    })
    return response.data
  },

  ping: async () => {
    const response = await axios.get(`${API_BASE_URL}/ping`)
    return response.data
  },

  getLabStatusOverview: async (windowMinutes = 120) => {
    const response = await axios.get(`${API_BASE_URL}/lab-status/overview?window_minutes=${encodeURIComponent(windowMinutes)}`)
    return response.data
  },

  // Insights operations
  getInsights: async (params = {}) => {
    const queryParams = new URLSearchParams()

    if (params.limit) queryParams.append('limit', params.limit)
    if (params.type) queryParams.append('type', params.type)
    if (params.priority_min) queryParams.append('priority_min', params.priority_min)
    if (params.unread_only) queryParams.append('unread_only', params.unread_only)
    if (params.verdict) queryParams.append('verdict', params.verdict)

    const response = await axios.get(`${API_BASE_URL}/insights?${queryParams}`)
    return response.data
  },

  getScanInsights: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/insights/scan/${scanId}`)
    return response.data
  },

  markInsightsRead: async (insightIds) => {
    const response = await axios.post(`${API_BASE_URL}/insights/mark-read`, {
      insight_ids: insightIds
    })
    return response.data
  },

  clearOldInsights: async (days = 30) => {
    const response = await axios.post(`${API_BASE_URL}/insights/clear-old`, {
      days
    })
    return response.data
  },

  // Smart diff
  getScanDiff: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/scan-diff/${scanId}`)
    return response.data
  },

  // Scan synchronization
  syncScans: async (mode = 'import_missing') => {
    const response = await axios.post(`${API_BASE_URL}/sync-scans`, { mode })
    return response.data
  },

  getSyncStatus: async () => {
    const response = await axios.get(`${API_BASE_URL}/sync-status`)
    return response.data
  },

  getScanHostContext: async (scanId) => {
    const response = await axios.get(`${API_BASE_URL}/scans/${scanId}/host-context`)
    return response.data
  },

  patchScanHostLabels: async (scanId, labels) => {
    const response = await axios.patch(`${API_BASE_URL}/scans/${scanId}/host-context/labels`, { labels })
    return response.data
  },

  // Hunter runs
  getHunterRuns: async (limit = 20) => {
    const response = await axios.get(`${API_BASE_URL}/hunter/runs?limit=${encodeURIComponent(limit)}`)
    return response.data
  },

  getLatestHunterRun: async () => {
    const response = await axios.get(`${API_BASE_URL}/hunter/runs/latest`)
    return response.data
  },

  getHunterRunById: async (runId) => {
    const response = await axios.get(`${API_BASE_URL}/hunter/runs/${encodeURIComponent(runId)}`)
    return response.data
  },

  getHunterOverview: async (limit = 20) => {
    const response = await axios.get(`${API_BASE_URL}/hunter/overview?limit=${encodeURIComponent(limit)}`)
    return response.data
  },

  getHunterMissions: async (limit = 20) => {
    const response = await axios.get(`${API_BASE_URL}/hunter/missions?limit=${encodeURIComponent(limit)}`)
    return response.data
  },

  getHunterMission: async (missionId) => {
    const response = await axios.get(`${API_BASE_URL}/hunter/missions/${encodeURIComponent(missionId)}`)
    return response.data
  },

  getHunterMissionLog: async (missionId) => {
    const response = await axios.get(`${API_BASE_URL}/hunter/missions/${encodeURIComponent(missionId)}/log`)
    return response.data
  },

  spawnHunterMission: async (seed) => {
    const response = await axios.post(`${API_BASE_URL}/hunter/missions`, seed)
    return response.data
  },
}
