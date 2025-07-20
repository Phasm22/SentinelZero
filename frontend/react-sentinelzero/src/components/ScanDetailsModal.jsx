import React, { useState, useEffect } from 'react'
import { apiService } from '../utils/api'
import { useToast } from '../contexts/ToastContext'
import { useUserPreferences } from '../contexts/UserPreferencesContext'
import { 
  BarChart3, 
  Monitor, 
  AlertTriangle, 
  FileText,
  X,
  Download,
  Eye
} from 'lucide-react'
import { formatTimestamp } from '../utils/date'

const ScanDetailsModal = ({ scan, isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState('overview')
  const [hosts, setHosts] = useState([])
  const [vulns, setVulns] = useState([])
  const [xmlData, setXmlData] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { showToast } = useToast()
  const { preferences } = useUserPreferences()

  const tabs = [
    { id: 'overview', name: 'Overview', icon: <BarChart3 className="w-4 h-4" /> },
    { id: 'hosts', name: 'Hosts', icon: <Monitor className="w-4 h-4" /> },
    { id: 'vulns', name: 'Vulnerabilities', icon: <AlertTriangle className="w-4 h-4" /> },
    { id: 'raw', name: 'Raw XML', icon: <FileText className="w-4 h-4" /> }
  ]

  useEffect(() => {
    if (isOpen && scan) {
      loadScanData()
    }
  }, [isOpen, scan])

  const loadScanData = async () => {
    if (!scan) return

    setIsLoading(true)
    try {
      const [hostsData, vulnsData, xmlData] = await Promise.all([
        apiService.getScanHosts(scan.id),
        apiService.getScanVulns(scan.id),
        apiService.getScanXml(scan.id)
      ])

      setHosts(hostsData.hosts || [])
      setVulns(vulnsData.vulns || [])
      setXmlData(xmlData)
    } catch (error) {
      console.error('Error loading scan data:', error)
      showToast('Failed to load scan details', 'danger')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDownloadXml = () => {
    if (!scan) return

    const blob = new Blob([xmlData], { type: 'application/xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `scan_${scan.id}.xml`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showToast('XML file downloaded', 'success')
  }

  if (!isOpen || !scan) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose}></div>

        <div className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full">
          {/* Header */}
          <div className="bg-gray-50 dark:bg-gray-700 px-6 py-4 border-b border-gray-200 dark:border-gray-600">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Scan Details - {scan.scan_type}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {formatTimestamp(scan.timestamp, preferences.use24Hour)}
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleDownloadXml}
                  className="btn btn-outline btn-sm flex items-center space-x-1"
                >
                  <Download className="w-4 h-4" />
                  <span>Download XML</span>
                </button>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="border-b border-gray-200 dark:border-gray-600">
            <nav className="flex space-x-8 px-6">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                  }`}
                >
                  {tab.icon}
                  <span>{tab.name}</span>
                </button>
              ))}
            </nav>
          </div>

          {/* Content */}
          <div className="px-6 py-6 max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
              </div>
            ) : (
              <>
                {/* Overview Tab */}
                {activeTab === 'overview' && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Scan Type</div>
                        <div className="text-lg font-semibold text-gray-900 dark:text-white">{scan.scan_type}</div>
                      </div>
                      <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Hosts Found</div>
                        <div className="text-lg font-semibold text-gray-900 dark:text-white">{hosts.length}</div>
                      </div>
                      <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Vulnerabilities</div>
                        <div className="text-lg font-semibold text-gray-900 dark:text-white">{vulns.length}</div>
                      </div>
                      <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Scan ID</div>
                        <div className="text-lg font-semibold text-gray-900 dark:text-white">#{scan.id}</div>
                      </div>
                    </div>

                    {/* Network Statistics */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Network Statistics</h3>
                      </div>
                      <div className="p-6">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Open Ports</div>
                            <div className="text-2xl font-bold text-gray-900 dark:text-white">
                              {hosts.reduce((total, host) => {
                                return total + (host.ports ? host.ports.length : 0)
                              }, 0)}
                            </div>
                          </div>
                          <div>
                            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Hosts with Services</div>
                            <div className="text-2xl font-bold text-gray-900 dark:text-white">
                              {hosts.filter(host => host.ports && host.ports.length > 0).length}
                            </div>
                          </div>
                          <div>
                            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Average Ports/Host</div>
                            <div className="text-2xl font-bold text-gray-900 dark:text-white">
                              {hosts.length > 0 
                                ? (hosts.reduce((total, host) => total + (host.ports ? host.ports.length : 0), 0) / hosts.length).toFixed(1)
                                : '0.0'
                              }
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Service Distribution */}
                    {hosts.length > 0 && (
                      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Service Distribution</h3>
                        </div>
                        <div className="p-6">
                          <div className="space-y-2">
                            {(() => {
                              const serviceCounts = {}
                              hosts.forEach(host => {
                                if (host.ports) {
                                  host.ports.forEach(port => {
                                    const service = port.service || 'unknown'
                                    serviceCounts[service] = (serviceCounts[service] || 0) + 1
                                  })
                                }
                              })
                              
                              return Object.entries(serviceCounts)
                                .sort(([,a], [,b]) => b - a)
                                .slice(0, 10)
                                .map(([service, count]) => (
                                  <div key={service} className="flex justify-between items-center">
                                    <span className="text-sm text-gray-900 dark:text-white capitalize">{service}</span>
                                    <span className="text-sm font-medium text-gray-500 dark:text-gray-400">{count}</span>
                                  </div>
                                ))
                            })()}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Scan Information */}
                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Scan Information</h3>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-gray-400">Timestamp:</span>
                          <span className="text-gray-900 dark:text-white">{formatTimestamp(scan.timestamp, preferences.use24Hour)}</span>
                        </div>
                        {scan.diff_from_previous && (
                          <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-gray-400">Changes from Previous:</span>
                            <span className="text-gray-900 dark:text-white">{scan.diff_from_previous}</span>
                          </div>
                        )}
                        {scan.raw_xml_path && (
                          <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-gray-400">XML File:</span>
                            <span className="text-gray-900 dark:text-white">{scan.raw_xml_path}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Hosts Tab */}
                {activeTab === 'hosts' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Discovered Hosts ({hosts.length})
                      </h3>
                    </div>
                    
                    {hosts.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                        <p>No hosts found in this scan.</p>
                      </div>
                    ) : (
                      <div className="space-y-6">
                        {hosts.map((host, index) => (
                          <div key={index} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
                            {/* Host Header */}
                            <div className="flex items-start justify-between mb-4">
                              <div className="flex-1">
                                <div className="flex items-center space-x-3 mb-2">
                                  <h4 className="text-lg font-semibold text-gray-900 dark:text-white font-mono">
                                    {host.ip || 'Unknown IP'}
                                  </h4>
                                  {host.mac && (
                                    <span className="text-sm text-gray-500 dark:text-gray-400 font-mono">
                                      {host.mac}
                                    </span>
                                  )}
                                </div>
                                {host.hostnames && host.hostnames.length > 0 && (
                                  <div className="text-sm text-gray-600 dark:text-gray-300">
                                    <span className="font-medium">Hostnames:</span> {host.hostnames.join(', ')}
                                  </div>
                                )}
                                {host.vendor && (
                                  <div className="text-sm text-gray-600 dark:text-gray-300">
                                    <span className="font-medium">Vendor:</span> {host.vendor}
                                  </div>
                                )}
                              </div>
                              <div className="text-right">
                                {host.distance && (
                                  <div className="text-sm text-gray-500 dark:text-gray-400">
                                    Distance: {host.distance} hops
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* OS Information */}
                            {host.os && (
                              <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                                <div className="flex items-center justify-between">
                                  <div>
                                    <span className="text-sm font-medium text-blue-800 dark:text-blue-200">OS Detection:</span>
                                    <div className="text-sm text-blue-700 dark:text-blue-300">
                                      {host.os.name} (Accuracy: {host.os.accuracy}%)
                                    </div>
                                  </div>
                                  {host.uptime && (
                                    <div className="text-right text-xs text-blue-600 dark:text-blue-400">
                                      <div>Uptime: {Math.floor(host.uptime.seconds / 86400)} days</div>
                                      <div>Last boot: {host.uptime.lastboot}</div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Ports and Services */}
                            {host.ports && host.ports.length > 0 ? (
                              <div>
                                <h5 className="text-md font-semibold text-gray-900 dark:text-white mb-3">
                                  Open Ports ({host.ports.length})
                                </h5>
                                <div className="overflow-x-auto">
                                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                    <thead className="bg-gray-50 dark:bg-gray-700">
                                      <tr>
                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                          Port
                                        </th>
                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                          Service
                                        </th>
                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                          Product
                                        </th>
                                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                          Version
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                      {host.ports.map((port, portIndex) => (
                                        <tr key={portIndex} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                                          <td className="px-3 py-2 whitespace-nowrap text-sm font-mono text-gray-900 dark:text-white">
                                            {port.port}/{port.protocol}
                                          </td>
                                          <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                                            {port.service || 'unknown'}
                                          </td>
                                          <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                                            {port.product || '-'}
                                          </td>
                                          <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                                            {port.version || '-'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            ) : (
                              <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                                <p>No open ports detected</p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Vulnerabilities Tab */}
                {activeTab === 'vulns' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Vulnerabilities ({vulns.length})
                      </h3>
                    </div>
                    
                    {vulns.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                        <p>No vulnerabilities found in this scan.</p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {vulns.map((vuln, index) => (
                          <div key={index} className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center space-x-2 mb-2">
                                  <h4 className="font-semibold text-red-800 dark:text-red-200">
                                    {vuln.id || 'Vulnerability Detected'}
                                  </h4>
                                  {vuln.host && (
                                    <span className="text-xs bg-red-100 dark:bg-red-800 text-red-700 dark:text-red-300 px-2 py-1 rounded">
                                      {vuln.host}
                                    </span>
                                  )}
                                </div>
                                {vuln.output && (
                                  <div className="text-red-700 dark:text-red-300 text-sm">
                                    <pre className="whitespace-pre-wrap font-mono text-xs bg-white dark:bg-gray-800 p-3 rounded border overflow-x-auto">
                                      {vuln.output}
                                    </pre>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Raw XML Tab */}
                {activeTab === 'raw' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Raw XML Data</h3>
                    </div>
                    
                    {xmlData ? (
                      <div className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-x-auto">
                        <pre className="text-xs">{xmlData}</pre>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                        <p>Loading XML data...</p>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ScanDetailsModal 