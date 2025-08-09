import React, { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'
import { 
  Settings as SettingsIcon,
  Save,
  RefreshCw,
  Bell,
  Shield,
  Network,
  Clock,
  Calendar,
  AlertTriangle,
  CheckCircle,
  AlertCircle
} from 'lucide-react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'
import Toggle from '../components/Toggle'
import Button from '../components/Button'
import Modal from '../components/Modal'

// Helper functions for network calculations
const netmaskToCidr = (netmask) => {
  if (!netmask) return 24
  const parts = netmask.split('.')
  let cidr = 0
  for (const part of parts) {
    const octet = parseInt(part, 10)
    for (let i = 7; i >= 0; i--) {
      if (octet & (1 << i)) cidr++
      else return cidr
    }
  }
  return cidr
}

const calculateNetworkAddress = (ip, netmask) => {
  if (!ip || !netmask) return ip
  const ipParts = ip.split('.').map(Number)
  const maskParts = netmask.split('.').map(Number)
  const networkParts = ipParts.map((part, i) => part & maskParts[i])
  return networkParts.join('.')
}

const Settings = () => {
  const { preferences, updatePreference } = useUserPreferences()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [showSaveConfirm, setShowSaveConfirm] = useState(false)
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false)
  const [networkInterfaces, setNetworkInterfaces] = useState({ interfaces: [] })
  const [originalSettings, setOriginalSettings] = useState(null)
  const { showToast } = useToast()
  
  // Settings state
  const [settings, setSettings] = useState({
    scheduledScans: {
      enabled: false,
      frequency: 'daily',
      time: '02:00',
      scanType: 'Full TCP',
      targetNetwork: '172.16.0.0/22'
    },
    notifications: {
      pushoverEnabled: false,
      pushoverConfigured: false,
      scanComplete: true,
      vulnerabilityFound: true,
      newHostFound: false
    },
    network: {
      defaultTargetNetwork: '172.16.0.0/22',
      maxHosts: 1000,
      scanTimeout: 300,
  concurrentScans: 1,
  preDiscoveryEnabled: false
    },
    security: {
      vulnScanningEnabled: true,
      osDetectionEnabled: true,
      serviceDetectionEnabled: true,
      aggressiveScanning: false
    }
  })

  const loadSettings = async () => {
    try {
      setIsLoading(true)
      const [data, interfacesResponse] = await Promise.all([
        apiService.getSettings(),
        apiService.getNetworkInterfaces()
      ])
      console.log('Loaded settings from API:', data)
      console.log('Loaded network interfaces from API:', interfacesResponse)
      
      // Always ensure we have a complete settings object, even if API call fails
      const mergedSettings = {
        scheduledScans: {
          enabled: false,
          frequency: 'daily',
          time: '02:00',
          scanType: 'Full TCP',
          targetNetwork: '172.16.0.0/22',
          ...(data?.scheduledScansSettings || {})
        },
        notifications: {
          pushoverEnabled: false,
          scanComplete: true,
          vulnerabilityFound: true,
          newHostFound: false,
          ...(data?.notificationSettings || {})
        },
        network: {
          defaultTargetNetwork: '172.16.0.0/22',
          maxHosts: 1000,
          scanTimeout: 300,
          concurrentScans: 1,
          preDiscoveryEnabled: false,
          ...(data?.networkSettings || {})
        },
        security: {
          vulnScanningEnabled: true,
          osDetectionEnabled: true,
          serviceDetectionEnabled: true,
          aggressiveScanning: false,
          ...(data?.securitySettings || {})
        }
      }
      
      setSettings(mergedSettings)
      // If backend didn't provide pushoverConfigured but we can infer from enabled + absence of error later, set true
  // Do not auto-set pushoverConfigured; rely on backend derived value
      const settingsStr = JSON.stringify(mergedSettings)
      console.log('Setting originalSettings to:', settingsStr)
      setOriginalSettings(settingsStr)
      
      // Extract the network interfaces response object
      console.log('Network interfaces API response:', interfacesResponse)
      setNetworkInterfaces(interfacesResponse || { interfaces: [] })
      console.log('Available network interfaces:', interfacesResponse?.interfaces?.length || 0)
      setIsLoading(false)
    } catch (error) {
      console.error('Error loading settings:', error)
      
      // Initialize with default settings even if API call fails
      const defaultSettings = {
        scheduledScans: {
          enabled: false,
          frequency: 'daily',
          time: '02:00',
          scanType: 'Full TCP',
          targetNetwork: '172.16.0.0/22'
        },
        notifications: {
          pushoverEnabled: false,
          pushoverConfigured: false,
          scanComplete: true,
          vulnerabilityFound: true,
          newHostFound: false
        },
        network: {
          defaultTargetNetwork: '172.16.0.0/22',
          maxHosts: 1000,
          scanTimeout: 300,
          concurrentScans: 1,
          preDiscoveryEnabled: false
        },
        security: {
          vulnScanningEnabled: true,
          osDetectionEnabled: true,
          serviceDetectionEnabled: true,
          aggressiveScanning: false
        }
      }
      
      setSettings(defaultSettings)
      setOriginalSettings(JSON.stringify(defaultSettings))
      setNetworkInterfaces({ interfaces: [] })
      setError('Failed to load settings')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  // (Removed auto-test of Pushover to avoid unwanted notifications on each visit)

  // Check for changes whenever settings change
  useEffect(() => {
    if (originalSettings) {
      // Use a more reliable deep comparison instead of JSON.stringify
      const currentSettingsStr = JSON.stringify(settings)
      const hasChanges = currentSettingsStr !== originalSettings
      console.log('Change detection:', {
        hasChanges,
        originalLength: originalSettings.length,
        currentLength: currentSettingsStr.length,
        originalStr: originalSettings.substring(0, 100) + '...',
        currentStr: currentSettingsStr.substring(0, 100) + '...'
      })
      setHasUnsavedChanges(hasChanges)
    }
  }, [JSON.stringify(settings), originalSettings])

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
      // Convert frontend format back to backend format
      const backendSettings = {
        scheduledScansSettings: settings.scheduledScans || {},
        notificationSettings: settings.notifications || {},
        networkSettings: settings.network || {},
        securitySettings: settings.security || {}
      }
      
      await apiService.updateSettings(backendSettings)
      showToast('Settings saved successfully', 'success')
      setOriginalSettings(JSON.stringify(settings))
      setHasUnsavedChanges(false)
      setShowSaveConfirm(false)
    } catch (error) {
      console.error('Error saving settings:', error)
      showToast('Failed to save settings', 'danger')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDiscardChanges = () => {
    loadSettings()
    setHasUnsavedChanges(false)
    setShowDiscardConfirm(false)
  }

  const testPushoverConnection = async () => {
    try {
      await apiService.testPushoverConnection()
      showToast('Pushover connection successful!', 'success')
    } catch (error) {
      showToast('Pushover connection failed. Check your configuration.', 'danger')
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
      {/* Action Buttons (responsive) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-end gap-2 sm:gap-3">
        <div className="flex flex-wrap items-center justify-end gap-2 sm:gap-3 w-full">
          {/* Debug info - hide on very small screens */}
          <div className="text-[10px] sm:text-xs text-gray-400 hidden xs:block">
            unsaved: {hasUnsavedChanges ? 'yes' : 'no'}
          </div>
          {/* Unsaved badge (compact on mobile) */}
          {hasUnsavedChanges && (
            <div className="flex items-center space-x-1 sm:space-x-2 text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 px-2 py-1 rounded-md">
              <AlertCircle className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="text-[11px] sm:text-sm font-medium">Unsaved</span>
            </div>
          )}
          {/* Test button (wraps) */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleSettingChange('network', 'maxHosts', Math.random() * 1000)}
            className="text-[11px] sm:text-xs px-2 py-1"
          >
            Test
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDiscardConfirm(true)}
            disabled={!hasUnsavedChanges}
            className="text-[11px] sm:text-xs px-2 py-1"
          >
            Discard
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={isSaving}
            onClick={() => setShowSaveConfirm(true)}
            disabled={false}
            className="flex items-center text-[11px] sm:text-xs px-2 py-1"
          >
            <Save className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
            {isSaving ? 'Saving' : 'Save'}
          </Button>
        </div>
      </div>

      {/* User Preferences */}
      <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-6">
        <div className="flex items-center space-x-2 mb-4">
          <SettingsIcon className="h-5 w-5 text-blue-500" />
          <h2 className="text-xl font-title font-bold text-gray-100">User Preferences</h2>
        </div>
        <div className="space-y-6">
          <div className="flex items-center justify-between w-full">
            <div className="flex flex-col items-start text-left w-full pr-4">
              <label className="text-sm font-medium text-gray-300 text-left">Use 24-hour time format</label>
              <p className="text-sm text-gray-400 text-left">Display timestamps in 24-hour format</p>
            </div>
            <Toggle
              checked={preferences.use24Hour}
              onChange={(checked) => updatePreference('use24Hour', checked)}
            />
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex flex-col text-left w-full sm:pr-4">
              <label className="text-sm font-medium text-gray-300">Theme</label>
              <p className="text-sm text-gray-400">Choose light, dark, or follow system preference</p>
            </div>
            <div className="w-full sm:w-56">
              <select
                value={preferences.theme || 'system'}
                onChange={(e) => updatePreference('theme', e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-100 text-sm"
              >
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Scheduled Scans */}
      <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl">
        <div className="px-6 py-4 border-b border-white/10 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <Clock className="h-5 w-5 text-green-500" />
            <h2 className="text-xl font-title font-bold text-gray-100">Scheduled Scans</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between w-full">
            <div className="flex flex-col items-start text-left w-full">
              <label className="text-sm font-medium text-gray-300 text-left">Enable Scheduled Scans</label>
              <p className="text-sm text-gray-400 text-left">Automatically run scans at specified intervals</p>
            </div>
            <Toggle
              checked={settings.scheduledScans?.enabled || false}
              onChange={(checked) => handleSettingChange('scheduledScans', 'enabled', checked)}
            />
          </div>

          {settings.scheduledScans?.enabled && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Frequency</label>
                  <select
                    value={settings.scheduledScans?.frequency || 'daily'}
                    onChange={(e) => handleSettingChange('scheduledScans', 'frequency', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-100"
                  >
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Time</label>
                  <input
                    type="time"
                    value={settings.scheduledScans?.time || '02:00'}
                    onChange={(e) => handleSettingChange('scheduledScans', 'time', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Scan Type</label>
                  <select
                    value={settings.scheduledScans?.scanType || 'Full TCP'}
                    onChange={(e) => handleSettingChange('scheduledScans', 'scanType', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-100"
                  >
                    <option value="Full TCP">Full TCP</option>
                    <option value="IoT Scan">IoT Scan</option>
                    <option value="Vuln Scripts">Vuln Scripts</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Target Network</label>
                  <input
                    type="text"
                    value={settings.scheduledScans?.targetNetwork || '172.16.0.0/22'}
                    onChange={(e) => handleSettingChange('scheduledScans', 'targetNetwork', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-100"
                    placeholder="172.16.0.0/22"
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Pushover Notifications */}
      <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl">
        <div className="px-6 py-4 border-b border-white/10 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Bell className="h-5 w-5 text-yellow-500" />
              <h2 className="text-xl font-title font-bold text-gray-100">Pushover Notifications</h2>
            </div>
            <div className="flex items-center space-x-2">
              {settings.notifications?.pushoverConfigured && (
                <div className="flex items-center space-x-1 text-green-400">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm">Configured</span>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between w-full">
            <div className="flex flex-col items-start text-left w-full">
              <label className="text-sm font-medium text-gray-300 text-left">Enable Pushover Notifications</label>
              <p className="text-sm text-gray-400 text-left">Send notifications to your mobile device</p>
            </div>
            <Toggle
              checked={settings.notifications?.pushoverEnabled || false}
              onChange={(checked) => handleSettingChange('notifications', 'pushoverEnabled', checked)}
            />
          </div>

          {settings.notifications?.pushoverEnabled && (
            <>
              <div className="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
                <div className="mb-3">
                  <h3 className="text-sm font-medium text-gray-300">Notification Types</h3>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm text-gray-300">Scan Complete</label>
                      <p className="text-xs text-gray-400">Notify when scheduled scans finish</p>
                    </div>
                    <Toggle
                      checked={settings.notifications.scanComplete}
                      onChange={(checked) => handleSettingChange('notifications', 'scanComplete', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm text-gray-300">Vulnerability Found</label>
                      <p className="text-xs text-gray-400">Notify when new vulnerabilities are detected</p>
                    </div>
                    <Toggle
                      checked={settings.notifications.vulnerabilityFound}
                      onChange={(checked) => handleSettingChange('notifications', 'vulnerabilityFound', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-sm text-gray-300">New Host Found</label>
                      <p className="text-xs text-gray-400">Notify when new hosts are discovered</p>
                    </div>
                    <Toggle
                      checked={settings.notifications.newHostFound}
                      onChange={(checked) => handleSettingChange('notifications', 'newHostFound', checked)}
                    />
                  </div>
                </div>
              </div>

              <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
                <div className="flex items-start space-x-2">
                  <AlertTriangle className="h-5 w-5 text-yellow-500 mt-0.5" />
                  <div>
                    <h3 className="text-sm font-medium text-yellow-300">Pushover Configuration</h3>
                    <p className="text-sm text-yellow-200 mt-1">
                      Pushover API keys are configured server-side for security. 
                      Contact your administrator to set up Pushover credentials.
                    </p>
                    <button
                      onClick={testPushoverConnection}
                      className="mt-2 text-sm text-yellow-300 hover:text-yellow-200 underline"
                    >
                      Test Connection
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Network Settings */}
      <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl">
        <div className="px-6 py-4 border-b border-white/10 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <Network className="h-5 w-5 text-blue-500" />
            <h2 className="text-xl font-title font-bold text-gray-100">Network Settings</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Default Target Network</label>
              <select
                value={settings.network.defaultTargetNetwork}
                onChange={(e) => handleSettingChange('network', 'defaultTargetNetwork', e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-100"
              >
                <optgroup label="Network Interfaces">
                  {(networkInterfaces?.interfaces || []).map((iface, index) => (
                    <option key={`interface-${index}`} value={iface.cidr}>
                      {iface.display}
                    </option>
                  ))}
                </optgroup>
                {networkInterfaces.common_networks && networkInterfaces.common_networks.length > 0 && (
                  <optgroup label="Common Networks">
                    {networkInterfaces.common_networks.map((network, index) => (
                      <option key={`common-${index}`} value={network.cidr}>
                        {network.display}
                      </option>
                    ))}
                  </optgroup>
                )}
                <option value="custom">Custom Network...</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Scan Timeout (seconds)</label>
              <input
                type="number"
                value={settings.network.scanTimeout}
                onChange={(e) => handleSettingChange('network', 'scanTimeout', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-100"
                min="60"
                max="3600"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Security Settings */}
      <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl">
        <div className="px-6 py-4 border-b border-white/10 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <Shield className="h-5 w-5 text-green-500" />
            <h2 className="text-xl font-title font-bold text-gray-100">Security Settings</h2>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between w-full">
            <div className="flex flex-col items-start text-left w-full">
              <label className="text-sm font-medium text-gray-300 text-left">Enable Vulnerability Scanning</label>
              <p className="text-sm text-gray-400 mb-0 text-left">Run vulnerability assessment scripts during scans</p>
            </div>
            <Toggle
              checked={settings.security.vulnScanningEnabled}
              onChange={(checked) => handleSettingChange('security', 'vulnScanningEnabled', checked)}
            />
          </div>
          <div className="flex items-center justify-between w-full">
            <div className="flex flex-col items-start text-left w-full">
              <label className="text-sm font-medium text-gray-300 text-left">Enable OS Detection</label>
              <p className="text-sm text-gray-400 mb-0 text-left">Attempt to detect operating systems of discovered hosts</p>
            </div>
            <Toggle
              checked={settings.security.osDetectionEnabled}
              onChange={(checked) => handleSettingChange('security', 'osDetectionEnabled', checked)}
            />
          </div>
          <div className="flex items-center justify-between w-full">
            <div className="flex flex-col items-start text-left w-full">
              <label className="text-sm font-medium text-gray-300 text-left">Enable Service Detection</label>
              <p className="text-sm text-gray-400 mb-0 text-left">Detect and identify services running on open ports</p>
            </div>
            <Toggle
              checked={settings.security.serviceDetectionEnabled}
              onChange={(checked) => handleSettingChange('security', 'serviceDetectionEnabled', checked)}
            />
          </div>
          <div className="flex items-center justify-between w-full">
            <div className="flex flex-col items-start text-left w-full">
              <label className="text-sm font-medium text-gray-300 text-left">Aggressive Scanning</label>
              <p className="text-sm text-gray-400 mb-0 text-left">Use more aggressive scan techniques (may trigger IDS)</p>
            </div>
            <Toggle
              checked={settings.security.aggressiveScanning}
              onChange={(checked) => handleSettingChange('security', 'aggressiveScanning', checked)}
            />
          </div>
        </div>
      </div>

      {/* System Information */}
      <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl">
        <div className="px-6 py-4 border-b border-white/10 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <RefreshCw className="h-5 w-5 text-purple-500" />
            <h2 className="text-xl font-title font-bold text-gray-100">System Information</h2>
          </div>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-400 font-medium">Application Version:</span>
              <span className="text-gray-100 ml-2">1.0.0</span>
            </div>
            <div>
              <span className="text-gray-400 font-medium">Database:</span>
              <span className="text-gray-100 ml-2">SQLite</span>
            </div>
            <div>
              <span className="text-gray-400 font-medium">Backend:</span>
              <span className="text-gray-100 ml-2">Flask + SocketIO</span>
            </div>
            <div>
              <span className="text-gray-400 font-medium">Frontend:</span>
              <span className="text-gray-100 ml-2">React + Vite</span>
            </div>
          </div>
        </div>
      </div>

      {/* Save Confirmation Modal */}
      <Modal
        isOpen={showSaveConfirm}
        onClose={() => setShowSaveConfirm(false)}
        title="Save Settings"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-gray-300">
            Are you sure you want to save these settings? This will update the application configuration.
          </p>
          <div className="flex justify-end space-x-3">
            <Button
              variant="ghost"
              onClick={() => setShowSaveConfirm(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={isSaving}
              onClick={handleSaveSettings}
            >
              Save Settings
            </Button>
          </div>
        </div>
      </Modal>

      {/* Discard Confirmation Modal */}
      <Modal
        isOpen={showDiscardConfirm}
        onClose={() => setShowDiscardConfirm(false)}
        title="Discard Changes"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-gray-300">
            Are you sure you want to discard all unsaved changes? This action cannot be undone.
          </p>
          <div className="flex justify-end space-x-3">
            <Button
              variant="ghost"
              onClick={() => setShowDiscardConfirm(false)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDiscardChanges}
            >
              Discard Changes
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default Settings 