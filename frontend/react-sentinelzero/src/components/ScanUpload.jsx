import React, { useState, useCallback } from 'react'
import { Upload, FileText, CheckCircle, AlertCircle } from 'lucide-react'
import { useToast } from '../contexts/ToastContext'
import { apiService } from '../utils/api'

const ScanUpload = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadedFile, setUploadedFile] = useState(null)
  const { showToast } = useToast()

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    
    const files = Array.from(e.dataTransfer.files)
    const xmlFile = files.find(file => file.name.endsWith('.xml'))
    
    if (xmlFile) {
      handleFileUpload(xmlFile)
    } else {
      showToast('Please upload an XML file', 'danger')
    }
  }, [])

  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file && file.name.endsWith('.xml')) {
      handleFileUpload(file)
    } else {
      showToast('Please select an XML file', 'danger')
    }
  }

  const handleFileUpload = async (file) => {
    setIsUploading(true)
    setUploadedFile(file)

    try {
      const formData = new FormData()
      formData.append('file', file)  // Changed from 'xml_file' to 'file'
      formData.append('scan_type', 'Manual Upload')

      const response = await apiService.uploadScan(formData)
      showToast('Scan uploaded successfully!', 'success')
      
      if (onUploadSuccess) {
        onUploadSuccess(response)
      }
    } catch (error) {
      console.error('Upload error:', error)
      showToast('Failed to upload scan results', 'danger')
      setUploadedFile(null)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-2xl p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-title font-bold text-gray-100">Upload Scan Results</h2>
        <FileText className="w-8 h-8 text-blue-400" />
      </div>

      {/* Command Example */}
      <div className="mb-6 p-4 bg-gray-900 rounded-lg">
        <h3 className="text-sm font-semibold text-gray-300 mb-2">Run this in your terminal:</h3>
        <pre className="text-xs text-green-400 overflow-x-auto">
          sudo nmap -v -T4 -sS -p- --open -O -sV -Pn \<br />
          &nbsp;&nbsp;--script=ssl-cert,ssl-enum-ciphers,http-title,ssh-hostkey \<br />
          &nbsp;&nbsp;192.168.68.0/22 -oX scan_results.xml
        </pre>
        <p className="text-xs text-gray-400 mt-2">
          Then drag and drop the scan_results.xml file below
        </p>
      </div>

      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 ${
          isDragging 
            ? 'border-blue-400 bg-blue-400/10' 
            : 'border-gray-600 hover:border-gray-500'
        } ${
          isUploading ? 'opacity-50 pointer-events-none' : ''
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isUploading ? (
          <div className="flex flex-col items-center space-y-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400"></div>
            <p className="text-gray-300">Processing {uploadedFile?.name}...</p>
          </div>
        ) : uploadedFile ? (
          <div className="flex flex-col items-center space-y-4">
            <CheckCircle className="w-12 h-12 text-green-400" />
            <p className="text-gray-300">✅ {uploadedFile.name} uploaded successfully</p>
            <button
              onClick={() => {
                setUploadedFile(null)
                document.getElementById('file-input').value = ''
              }}
              className="btn btn-outline btn-sm"
            >
              Upload Another
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-4">
            <Upload className={`w-12 h-12 ${isDragging ? 'text-blue-400' : 'text-gray-400'}`} />
            <div>
              <p className="text-lg font-medium text-gray-300">
                Drop your nmap XML file here
              </p>
              <p className="text-sm text-gray-400">
                or click to browse files
              </p>
            </div>
            <input
              id="file-input"
              type="file"
              accept=".xml"
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => document.getElementById('file-input').click()}
              className="btn btn-primary"
            >
              Choose File
            </button>
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="mt-6 p-4 bg-blue-900/20 border border-blue-700/30 rounded-lg">
        <div className="flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm">
            <p className="text-blue-200 font-medium mb-1">macOS Wi-Fi Scanning Note:</p>
            <p className="text-blue-300">
              Manual terminal scanning with sudo provides more reliable results on macOS Wi-Fi networks. 
              The uploaded XML will be parsed and imported into your scan history.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ScanUpload
