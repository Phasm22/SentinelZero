import React from 'react'
import { Rocket, Cpu, Bug, Loader2 } from 'lucide-react'

const buildNmapCommand = (scanType, security, targetNetwork = '172.16.0.0/22') => {
  // Handle null or undefined scanType
  if (!scanType) {
    return 'nmap -v -T4 -Pn -sS -p- --open 172.16.0.0/22 -oX scan_output.xml'
  }
  
  // Normalize early so we can decide baseline flags
  const scanTypeNormalized = String(scanType).toLowerCase()
  // Baseline flags; omit -Pn for discovery so nmap performs real host discovery
  const isDiscovery = scanTypeNormalized === 'discovery scan'
  let cmd = isDiscovery ? ['nmap', '-v', '-T4'] : ['nmap', '-v', '-T4', '-Pn']
  // (scanTypeNormalized already defined above)
  
  if (scanTypeNormalized === 'full tcp') {
    cmd.push('-sS', '-p-', '--open')
  } else if (scanTypeNormalized === 'iot scan') {
    cmd.push('-sU', '-p', '53,67,68,80,443,1900,5353,554,8080')
  } else if (scanTypeNormalized === 'discovery scan') {
    cmd.push('-sn', '-PE', '-PP', '-PM', '-PR', '-n', '--max-retries', '1', '-T4')
  } else if (scanTypeNormalized === 'vuln scripts') {
    cmd.push('-sS', '-p-', '--open')
  }
  
  // Apply security settings - match backend exactly
  if (security.osDetectionEnabled) cmd.push('-O')
  if (security.serviceDetectionEnabled) cmd.push('-sV')
  
  if (scanTypeNormalized === 'vuln scripts') {
    // Only run vulnerability scripts for explicit vulnerability scans
    cmd.push('--script=vuln')
  } else if (security.vulnScanningEnabled) {
    // Use more targeted vulnerability scripts for regular scans
    cmd.push('--script=ssl-cert,ssl-enum-ciphers,http-title,ssh-hostkey')
  }
  
  if (security.aggressiveScanning) cmd.push('-A')
  cmd.push(targetNetwork, '-oX', 'scan_output.xml')
  return cmd.join(' ')
}

const ScanControls = ({
  isScanning,
  scanningType,
  scanProgress,
  scanStatus,
  scanMessage,
  isConnected,
  onRequestScan,
}) => {
  const DisconnectedDot = () => (
    <span className="relative flex h-3 w-3">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
    </span>
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-4">
        <button
          data-testid="scan-discovery-btn"
          onClick={() => onRequestScan('Discovery Scan')}
          // Allow Discovery Scan even if a heavy scan is running; only disable if another Discovery Scan is in progress
          disabled={isScanning && scanningType === 'Discovery Scan'}
          title="Lightweight host discovery only (no ports)."
          className="btn flex items-center space-x-2 px-6 py-3 text-lg font-bold bg-green-700 hover:bg-green-800 focus:ring-2 focus:ring-green-400 shadow-lg transition-all duration-200 rounded-xl text-white relative group"
        >
          <Rocket className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform rotate-180" />
          <span>Discovery Scan</span>
          {isScanning && scanningType === 'Discovery Scan' && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
        </button>
        <button
          data-testid="scan-full-tcp-btn"
          onClick={() => onRequestScan('Full TCP')}
          disabled={isScanning}
          title="Full TCP SYN scan of all ports. If Pre-Discovery is enabled only live hosts are scanned."
          className="btn flex items-center space-x-2 px-6 py-3 text-lg font-bold bg-blue-600 hover:bg-blue-700 focus:ring-2 focus:ring-blue-400 shadow-lg transition-all duration-200 rounded-xl text-white relative group"
        >
          <Rocket className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform" />
          <span>Full TCP Scan</span>
          {isScanning && scanningType === 'Full TCP' && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
        </button>
        <button
          data-testid="scan-iot-btn"
          onClick={() => onRequestScan('IoT Scan')}
          disabled={isScanning}
          title="Common IoT UDP/TCP service ports. Pre-Discovery narrows hosts first if enabled."
          className="btn flex items-center space-x-2 px-6 py-3 text-lg font-bold bg-gray-800 hover:bg-purple-700 focus:ring-2 focus:ring-purple-400 shadow-lg transition-all duration-200 rounded-xl text-white relative group"
        >
          <Cpu className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform" />
          <span>IoT Scan</span>
          {isScanning && scanningType === 'IoT Scan' && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
        </button>
        <button
          data-testid="scan-vuln-btn"
          onClick={() => onRequestScan('Vuln Scripts')}
          disabled={isScanning}
          title="Full TCP plus vulnerability scripts. Pre-Discovery reduces host set first if enabled."
          className="btn flex items-center space-x-2 px-6 py-3 text-lg font-bold bg-gray-700 hover:bg-red-700 focus:ring-2 focus:ring-red-400 shadow-lg transition-all duration-200 rounded-xl text-white relative group"
        >
          <Bug className="w-8 h-8 mr-2 text-red-400 group-hover:scale-125 transition-transform" />
          <span>Vuln Scripts</span>
          {isScanning && scanningType === 'Vuln Scripts' && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
        </button>
      </div>

      {/* Connection Status */}
      {!isConnected && (
        <div className="flex items-center space-x-2 text-red-400 bg-red-900/20 border border-red-700/30 rounded-lg p-3">
          <DisconnectedDot />
          <span className="text-sm font-medium">Scanner Disconnected</span>
          <span className="text-xs text-red-300">- Try uploading manual scan results instead</span>
        </div>
      )}

      {/* Progress Bar */}
      {isScanning && (
        <div className="mt-4">
          {scanMessage && (
            <div className="mb-2 text-sm font-medium text-blue-200">{scanMessage}</div>
          )}
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-300">
              Scan in Progress...
            </span>
            <span className="text-sm text-gray-400">
              {scanProgress ? `${Math.round(scanProgress)}%` : '0%'}
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
            <div
              className="bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 h-2 rounded-full animate-pulse transition-all duration-300"
              style={{ width: `${scanProgress || 0}%` }}
            ></div>
          </div>
        </div>
      )}
    </div>
  )
}

export { buildNmapCommand }
export default ScanControls 