import React, { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import { 
  Settings as SettingsIcon,
  Save,
  RefreshCw,
  Bell,
  Shield,
  Network
} from 'lucide-react'

const Settings = () => {
  const [settings, setSettings] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const { showToast } = useToast()

  const loadSettings = async () => {
    try {
      const data = await apiService.getSettings()
      setSettings(data)
      setIsLoading(false)
    } catch (error) {
      console.error('Error loading settings:', error)
      setError('Failed to load settings')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const handleSettingChange = (section, key, value) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }))
  }

  const handleSaveSettings = async () => {
    setIsSaving(true)
    try {
      // Save each setting
      for (const [section, sectionSettings] of Object.entries(settings)) {
        for (const [key, value] of Object.entries(sectionSettings)) {
          await apiService.updateSetting(section, key, value)
        }
      }
      showToast('Settings saved successfully', 'success')
    } catch (error) {
      console.error('Error saving settings:', error)
      showToast('Failed to save settings', 'danger')
    } finally {
      setIsSaving(false)
    }
  }

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
        <SettingsIcon className="mx-auto h-12 w-12 text-red-500" />
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
          <p className="text-gray-600 dark:text-gray-400">Configure application preferences</p>
        </div>
        <button
          onClick={handleSaveSettings}
          disabled={isSaving}
          className="btn btn-primary flex items-center space-x-2"
        >
          <Save className="w-4 h-4" />
          <span>{isSaving ? 'Saving...' : 'Save Settings'}</span>
        </button>
      </div>

      {/* Network Settings */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <Network className="h-5 w-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Network Settings</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Target Network
            </label>
            <input
              type="text"
              value={settings.network?.target_network || '172.16.0.0/22'}
              onChange={(e) => handleSettingChange('network', 'target_network', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="172.16.0.0/22"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              The network range to scan (CIDR notation)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Max Hosts to Scan
            </label>
            <input
              type="number"
              value={settings.network?.max_hosts || 1000}
              onChange={(e) => handleSettingChange('network', 'max_hosts', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              min="1"
              max="10000"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Maximum number of hosts to scan in large networks
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Scan Timeout (seconds)
            </label>
            <input
              type="number"
              value={settings.network?.scan_timeout || 300}
              onChange={(e) => handleSettingChange('network', 'scan_timeout', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              min="60"
              max="3600"
            />
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Maximum time to wait for scan completion
            </p>
          </div>
        </div>
      </div>

      {/* Notification Settings */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <Bell className="h-5 w-5 text-yellow-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Notification Settings</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable Pushover Notifications
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Send notifications to your mobile device
              </p>
            </div>
            <input
              type="checkbox"
              checked={settings.notifications?.pushover_enabled || false}
              onChange={(e) => handleSettingChange('notifications', 'pushover_enabled', e.target.checked)}
              className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Pushover API Token
            </label>
            <input
              type="password"
              value={settings.notifications?.pushover_token || ''}
              onChange={(e) => handleSettingChange('notifications', 'pushover_token', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="Your Pushover API token"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Pushover User Key
            </label>
            <input
              type="password"
              value={settings.notifications?.pushover_user_key || ''}
              onChange={(e) => handleSettingChange('notifications', 'pushover_user_key', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="Your Pushover user key"
            />
          </div>
        </div>
      </div>

      {/* Security Settings */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <Shield className="h-5 w-5 text-green-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Security Settings</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable Vulnerability Scanning
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Run vulnerability assessment scripts during scans
              </p>
            </div>
            <input
              type="checkbox"
              checked={settings.security?.vuln_scanning_enabled || true}
              onChange={(e) => handleSettingChange('security', 'vuln_scanning_enabled', e.target.checked)}
              className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable OS Detection
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Attempt to detect operating systems of discovered hosts
              </p>
            </div>
            <input
              type="checkbox"
              checked={settings.security?.os_detection_enabled || true}
              onChange={(e) => handleSettingChange('security', 'os_detection_enabled', e.target.checked)}
              className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable Service Detection
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Detect and identify services running on open ports
              </p>
            </div>
            <input
              type="checkbox"
              checked={settings.security?.service_detection_enabled || true}
              onChange={(e) => handleSettingChange('security', 'service_detection_enabled', e.target.checked)}
              className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            />
          </div>
        </div>
      </div>

      {/* System Information */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <RefreshCw className="h-5 w-5 text-purple-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">System Information</h2>
          </div>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400 font-medium">Application Version:</span>
              <span className="text-gray-900 dark:text-white ml-2">1.0.0</span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400 font-medium">Database:</span>
              <span className="text-gray-900 dark:text-white ml-2">SQLite</span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400 font-medium">Backend:</span>
              <span className="text-gray-900 dark:text-white ml-2">Flask + SocketIO</span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400 font-medium">Frontend:</span>
              <span className="text-gray-900 dark:text-white ml-2">React + Vite</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings 