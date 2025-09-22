import React, { useState } from 'react'
import { Rocket, Upload, Settings, Play } from 'lucide-react'
import ScanControls from './ScanControls'
import ScanUploader from './ScanUploader'

const ScanningSection = ({
  onRequestScan,
  isScanning,
  scanningType,
  scanProgress,
  scanStatus,
  scanMessage,
  isConnected,
  onUploadComplete,
  onUploadError,
}) => {
  const [activeTab, setActiveTab] = useState('automated')

  const tabs = [
    { 
      id: 'automated', 
      name: 'Automated Scan', 
      icon: <Rocket className="w-4 h-4" />,
      description: 'Run automated scans with real-time progress'
    },
    { 
      id: 'upload', 
      name: 'Upload Results', 
      icon: <Upload className="w-4 h-4" />,
      description: 'Upload XML from manual terminal scans'
    }
  ]

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-2xl" data-testid="scanning-section">
      {/* Tab Navigation */}
      <div className="flex border-b border-gray-700" data-testid="scanning-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center space-x-2 px-6 py-4 font-medium transition-all duration-200 first:rounded-tl-2xl last:rounded-tr-2xl ${
              activeTab === tab.id
                ? 'bg-blue-600/20 text-blue-300 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
            }`}
            data-testid={`scanning-tab-${tab.id}`}
          >
            {tab.icon}
            <span className="font-semibold">{tab.name}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6" data-testid="scanning-content">
        {activeTab === 'automated' && (
          <div data-testid="automated-scan-tab">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-gray-100 mb-2" data-testid="automated-scan-title">Network Scanning</h3>
              <p className="text-gray-400 text-sm" data-testid="automated-scan-description">
                {isConnected 
                  ? 'Choose a scan type to begin automated network discovery' 
                  : 'Scanner disconnected - try uploading manual scan results instead'
                }
              </p>
            </div>
            <ScanControls
              onRequestScan={onRequestScan}
              isScanning={isScanning}
              scanningType={scanningType}
              scanProgress={scanProgress}
              scanStatus={scanStatus}
              scanMessage={scanMessage}
              isConnected={isConnected}
            />
          </div>
        )}

        {activeTab === 'upload' && (
          <div data-testid="upload-scan-tab">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-gray-100 mb-2" data-testid="upload-scan-title">Manual Scan Upload</h3>
              <p className="text-gray-400 text-sm" data-testid="upload-scan-description">
                Upload XML results from terminal scans - ideal for macOS WiFi or privileged scanning
              </p>
            </div>
            <ScanUploader
              onUploadComplete={onUploadComplete}
              onError={onUploadError}
            />
          </div>
        )}
      </div>

      {/* Quick Action Hint */}
      {!isScanning && (
        <div className="px-6 pb-4" data-testid="scanning-hint">
          <div className="flex items-center space-x-2 text-xs text-gray-500" data-testid="hint-content">
            <Settings className="w-3 h-3" />
            <span data-testid="hint-text">
              {activeTab === 'automated' 
                ? 'Automated scans will show real-time progress and results' 
                : 'Uploaded scans are processed immediately and appear in scan history'
              }
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default ScanningSection
