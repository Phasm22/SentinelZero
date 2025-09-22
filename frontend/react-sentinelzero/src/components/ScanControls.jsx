import React from 'react'
import { Rocket, Cpu, Bug, Loader2 } from 'lucide-react'
import Button from './Button'

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
    // Use very conservative parameters to prevent firewall state table overflow
    cmd.push('-sS', '--top-ports', '100', '--open', '--max-retries', '1', '--max-scan-delay', '500ms', '--min-rate', '50', '--max-rate', '200', '--scan-delay', '100ms')
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
        <Button
          data-testid="scan-discovery-btn"
          onClick={() => onRequestScan('Discovery Scan')}
          disabled={isScanning && scanningType === 'Discovery Scan'}
          loading={isScanning && scanningType === 'Discovery Scan'}
          variant="discovery-scan"
          size="lg"
          icon={<Rocket className="w-5 h-5 rotate-180" />}
          title="Lightweight host discovery only (no ports)."
        >
          Discovery Scan
        </Button>
        <Button
          data-testid="scan-full-tcp-btn"
          onClick={() => onRequestScan('Full TCP')}
          disabled={isScanning}
          loading={isScanning && scanningType === 'Full TCP'}
          variant="full-tcp"
          size="lg"
          icon={<Rocket className="w-5 h-5" />}
          title="Full TCP SYN scan of all ports. If Pre-Discovery is enabled only live hosts are scanned."
        >
          Full TCP Scan
        </Button>
        <Button
          data-testid="scan-iot-btn"
          onClick={() => onRequestScan('IoT Scan')}
          disabled={isScanning}
          loading={isScanning && scanningType === 'IoT Scan'}
          variant="iot-scan"
          size="lg"
          icon={<Cpu className="w-5 h-5" />}
          title="Common IoT UDP/TCP service ports. Pre-Discovery narrows hosts first if enabled."
        >
          IoT Scan
        </Button>
        <Button
          data-testid="scan-vuln-btn"
          onClick={() => onRequestScan('Vuln Scripts')}
          disabled={isScanning}
          loading={isScanning && scanningType === 'Vuln Scripts'}
          variant="vuln-scan"
          size="lg"
          icon={<Bug className="w-5 h-5" />}
          title="Full TCP plus vulnerability scripts. Pre-Discovery reduces host set first if enabled."
        >
          Vuln Scripts
        </Button>
      </div>

      {/* Connection Status */}
      {!isConnected && (
        <div className="flex items-center space-x-2 text-red-400 bg-red-900/20 border border-red-700/30 rounded-lg p-3" data-testid="connection-status">
          <DisconnectedDot />
          <span className="text-sm font-medium" data-testid="disconnected-text">Scanner Disconnected</span>
          <span className="text-xs text-red-300" data-testid="disconnected-hint">- Try uploading manual scan results instead</span>
        </div>
      )}

      {/* Progress Bar */}
      {isScanning && (
        <div className="mt-4" data-testid="scan-progress-section">
          {scanMessage && (
            <div className="mb-2 text-sm font-medium text-blue-200" data-testid="scan-message">{scanMessage}</div>
          )}
          <div className="flex items-center justify-between mb-2" data-testid="progress-header">
            <span className="text-sm font-medium text-gray-300" data-testid="progress-label">
              Scan in Progress...
            </span>
            <span className="text-sm text-gray-400" data-testid="progress-percentage">
              {scanProgress ? `${Math.round(scanProgress)}%` : '0%'}
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden" data-testid="progress-bar-container">
            <div
              className="bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 h-2 rounded-full animate-pulse transition-all duration-300"
              style={{ width: `${scanProgress || 0}%` }}
              data-testid="progress-bar-fill"
            ></div>
          </div>
        </div>
      )}
    </div>
  )
}

export { buildNmapCommand }
export default ScanControls 