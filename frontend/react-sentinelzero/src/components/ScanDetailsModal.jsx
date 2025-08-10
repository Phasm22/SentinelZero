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
  const [scanDetails, setScanDetails] = useState(scan)
  const [diffData, setDiffData] = useState(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const { showToast } = useToast()
  const { preferences } = useUserPreferences()

  const tabs = [
    { id: 'overview', name: 'Overview', icon: <BarChart3 className="w-4 h-4" /> },
    { id: 'diff', name: 'Diff', icon: <Eye className="w-4 h-4" /> },
    { id: 'hosts', name: 'Hosts', icon: <Monitor className="w-4 h-4" /> },
    { id: 'vulns', name: 'Vulnerabilities', icon: <AlertTriangle className="w-4 h-4" /> },
    { id: 'raw', name: 'Raw XML', icon: <FileText className="w-4 h-4" /> }
  ]

  useEffect(() => {
    if (isOpen && scan) {
      loadScanData()
    }
  }, [isOpen, scan])

  useEffect(() => {
    if (activeTab === 'diff' && diffData == null && scan) {
      loadDiff()
    }
  }, [activeTab, diffData, scan])

  const loadScanData = async () => {
    if (!scan) return

    setIsLoading(true)
    try {
      // Fetch full scan details
      const scanData = await apiService.getScan(scan.id)
      setScanDetails(scanData)
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

  const loadDiff = async () => {
    if (!scan) return
    setDiffLoading(true)
    try {
      const data = await apiService.getScanDiff(scan.id)
      setDiffData(data)
    } catch (e) {
      console.error('Error loading diff:', e)
      setDiffData({ error: 'Failed to load diff' })
    } finally {
      setDiffLoading(false)
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

  if (!isOpen || !scanDetails) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" data-testid="scan-details-modal">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} data-testid="modal-overlay"></div>

        <div className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full" data-testid="modal-content">
          {/* Header */}
          <div className="bg-gray-50 dark:bg-gray-700 px-6 py-4 border-b border-gray-200 dark:border-gray-600">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Scan Details - {scanDetails.scan_type}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {formatTimestamp(scanDetails.timestamp, preferences.use24Hour)}
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleDownloadXml}
                  className="btn btn-outline btn-sm flex items-center space-x-1"
                  data-testid="download-xml-btn"
                >
                  <Download className="w-4 h-4" />
                  <span>Download XML</span>
                </button>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  data-testid="close-modal-btn"
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
                  data-testid={`modal-tab-btn-${tab.id}`}
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
                        <div className="text-lg font-semibold text-gray-900 dark:text-white">{scanDetails.scan_type}</div>
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
                        <div className="text-lg font-semibold text-gray-900 dark:text-white">#{scanDetails.id}</div>
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
                          <span className="text-gray-900 dark:text-white">{formatTimestamp(scanDetails.timestamp, preferences.use24Hour)}</span>
                        </div>
                        {scanDetails.diff_from_previous && (
                          <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-gray-400">Changes from Previous:</span>
                            <span className="text-gray-900 dark:text-white">{scanDetails.diff_from_previous}</span>
                          </div>
                        )}
                        {scanDetails.raw_xml_path && (
                          <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-gray-400">XML File:</span>
                            <span className="text-gray-900 dark:text-white">{scanDetails.raw_xml_path}</span>
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

                {/* Diff Tab */}
                {activeTab === 'diff' && (
                  <div className="space-y-4">
                    {diffLoading ? (
                      <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
                      </div>
                    ) : diffData && diffData.error ? (
                      <div className="text-center py-8 text-red-400 text-sm">{diffData.error}</div>
                    ) : diffData == null ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">Diff not loaded.</div>
                    ) : (
                      <div className="space-y-6">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                          <StatBox label="New Hosts" value={diffData.summary?.new_hosts} />
                          <StatBox label="Removed Hosts" value={diffData.summary?.removed_hosts} />
                          <StatBox label="New Ports" value={diffData.summary?.new_ports} />
                          <StatBox label="Closed Ports" value={diffData.summary?.closed_ports} />
                          <StatBox label="New Vulns" value={diffData.summary?.new_vulns} />
                          <StatBox label="Resolved Vulns" value={diffData.summary?.resolved_vulns} />
                        </div>
                        {diffData.baseline && (
                          <div className="p-3 bg-blue-900/20 border border-blue-700/40 rounded text-xs text-blue-300">
                            Baseline scan for type – no previous scan to diff against.
                          </div>
                        )}
                        <Section title="New Hosts" items={diffData.hosts?.new} empty="No new hosts" />
                        <Section title="Removed Hosts" items={diffData.hosts?.removed} empty="No removed hosts" />
                        {diffData.hosts?.changed?.length > 0 && (
                          <div>
                            <h4 className="text-md font-semibold text-gray-900 dark:text-white mb-2">Changed Hosts</h4>
                            <div className="space-y-3">
                              {diffData.hosts.changed.map(h => (
                                <div key={h.ip} className="p-3 border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-xs">
                                  <div className="font-mono text-sm mb-1 text-primary-400">{h.ip}</div>
                                  {h.new_ports.length > 0 && (
                                    <div className="mb-1"><span className="font-semibold text-green-400">+ Ports:</span> {h.new_ports.map(p => `${p.port}/${p.protocol || ''}${p.service ? ' ('+p.service+')' : ''}`).join(', ')}</div>
                                  )}
                                  {h.closed_ports.length > 0 && (
                                    <div><span className="font-semibold text-red-400">- Ports:</span> {h.closed_ports.join(', ')}</div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div>
                            <h4 className="text-md font-semibold text-gray-900 dark:text-white mb-2">New Vulnerabilities</h4>
                            {diffData.vulns?.new?.length === 0 ? (
                              <div className="text-xs text-gray-500">None</div>
                            ) : (
                              <ul className="space-y-2 text-xs">
                                {diffData.vulns.new.map(v => (
                                  <li key={v.id + v.host} className="p-2 rounded bg-red-900/20 border border-red-700/30">
                                    <span className="font-mono text-red-300">{v.id}</span> <span className="text-gray-400">@ {v.host}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                          <div>
                            <h4 className="text-md font-semibold text-gray-900 dark:text-white mb-2">Resolved Vulnerabilities</h4>
                            {diffData.vulns?.resolved?.length === 0 ? (
                              <div className="text-xs text-gray-500">None</div>
                            ) : (
                              <ul className="space-y-2 text-xs">
                                {diffData.vulns.resolved.map(v => (
                                  <li key={v.id + v.host} className="p-2 rounded bg-green-900/20 border border-green-700/30">
                                    <span className="font-mono text-green-300">{v.id}</span> <span className="text-gray-400">@ {v.host}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        </div>
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
                      <div className="space-y-6">
                        {/* Group by host and CPE if present */}
                        {(() => {
                          // Group by host and CPE
                          const grouped = {}
                          vulns.forEach(v => {
                            const key = v.host + (v.cpe ? '|' + v.cpe : '')
                            if (!grouped[key]) grouped[key] = { host: v.host, cpe: v.cpe, vulns: [] }
                            grouped[key].vulns.push(v)
                          })
                          return Object.values(grouped).map((group, idx) => (
                            <div key={group.host + (group.cpe || '') + idx} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                              <div className="mb-2">
                                <span className="font-semibold text-gray-900 dark:text-white">Host:</span> <span className="font-mono">{group.host}</span>
                                {group.cpe && <span className="ml-4 text-xs text-blue-400">CPE: {group.cpe}</span>}
                                </div>
                              <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                                  <thead className="bg-gray-50 dark:bg-gray-700">
                                    <tr>
                                      <th className="px-3 py-2 text-left font-bold text-gray-500 dark:text-gray-300 uppercase tracking-wider">ID</th>
                                      <th className="px-3 py-2 text-left font-bold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Score</th>
                                      <th className="px-3 py-2 text-left font-bold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Link</th>
                                      <th className="px-3 py-2 text-left font-bold text-gray-500 dark:text-gray-300 uppercase tracking-wider">Exploit</th>
                                    </tr>
                                  </thead>
                                  <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                    {group.vulns.map((v, i) => (
                                      <tr key={v.id + v.url + i} className={v.exploit ? 'bg-red-50 dark:bg-red-900/20' : ''}>
                                        <td className="px-3 py-2 font-mono text-gray-900 dark:text-white">{v.id}</td>
                                        <td className="px-3 py-2 text-gray-900 dark:text-white">{v.score}</td>
                                        <td className="px-3 py-2 text-blue-600 dark:text-blue-300 underline"><a href={v.url} target="_blank" rel="noopener noreferrer">{v.url}</a></td>
                                        <td className="px-3 py-2 text-center">{v.exploit ? <span className="text-red-600 dark:text-red-300 font-bold">Yes</span> : <span className="text-gray-400">No</span>}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ))
                        })()}
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

// Helper components appended
const StatBox = ({ label, value }) => (
  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 text-center">
    <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400 font-semibold">{label}</div>
    <div className="text-lg font-bold text-gray-900 dark:text-white">{value ?? 0}</div>
  </div>
)

const Section = ({ title, items, empty }) => (
  <div>
    <h4 className="text-md font-semibold text-gray-900 dark:text-white mb-2">{title}</h4>
    {(!items || items.length === 0) ? (
      <div className="text-xs text-gray-500">{empty}</div>
    ) : (
      <div className="flex flex-wrap gap-2">
        {items.map(x => (
          <span key={x} className="px-2 py-1 text-xs rounded bg-gray-800 text-gray-200 font-mono">{x}</span>
        ))}
      </div>
    )}
  </div>
)