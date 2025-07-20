import axios from 'axios'

const API_BASE_URL = '/api'

export const apiService = {
  // Scan operations
  triggerScan: async (scanType) => {
    const response = await axios.post('/scan', 
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

  clearScan: async (scanId) => {
    const response = await axios.post(`/clear-scan/${scanId}`)
    return response.data
  },

  clearAllData: async () => {
    const response = await axios.post('/clear-all-data')
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

  updateSetting: async (section, key, value) => {
    const response = await axios.post(`${API_BASE_URL}/settings`, {
      section,
      key,
      value,
    })
    return response.data
  },
} 