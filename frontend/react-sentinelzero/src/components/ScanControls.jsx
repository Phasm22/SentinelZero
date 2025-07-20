import React from 'react'
import { Rocket, Cpu, Bug, Loader2 } from 'lucide-react'

const ScanControls = ({
  onScanTrigger,
  isScanning,
  scanProgress,
  isConnected,
}) => {
  const DisconnectedDot = () => (
    <span className="relative flex h-3 w-3">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
    </span>
  )

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-2xl p-8 flex flex-col gap-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-2xl font-title font-bold text-gray-100">Scan Controls</h2>
        <div className="flex items-center space-x-2">
          {!isConnected && (
            <div className="flex items-center space-x-2 text-red-500" title="Scanner not connected to agent">
              <DisconnectedDot />
              <span className="text-sm font-semibold">Disconnected</span>
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-4">
        <button
          onClick={() => onScanTrigger('Full TCP')}
          disabled={isScanning}
          className="btn flex items-center space-x-2 px-6 py-3 text-lg font-bold bg-blue-600 hover:bg-blue-700 focus:ring-2 focus:ring-blue-400 shadow-lg transition-all duration-200 rounded-xl text-white relative group"
        >
          <Rocket className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform" />
          <span>Full TCP Scan</span>
          {isScanning && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
        </button>
        <button
          onClick={() => onScanTrigger('IoT Scan')}
          disabled={isScanning}
          className="btn flex items-center space-x-2 px-6 py-3 text-lg font-bold bg-gray-800 hover:bg-purple-700 focus:ring-2 focus:ring-purple-400 shadow-lg transition-all duration-200 rounded-xl text-white relative group"
        >
          <Cpu className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform" />
          <span>IoT Scan</span>
        </button>
        <button
          onClick={() => onScanTrigger('Vuln Scripts')}
          disabled={isScanning}
          className="btn flex items-center space-x-2 px-6 py-3 text-lg font-bold bg-gray-700 hover:bg-red-700 focus:ring-2 focus:ring-red-400 shadow-lg transition-all duration-200 rounded-xl text-white relative group"
        >
          <Bug className="w-8 h-8 mr-2 text-red-400 group-hover:scale-125 transition-transform" />
          <span>Vuln Scripts</span>
        </button>
      </div>
      {/* Progress Bar */}
      {isScanning && (
        <div className="mt-4">
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

export default ScanControls 