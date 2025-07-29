import React, { useState } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle } from 'lucide-react';

const ScanUploader = ({ onUploadComplete, onError }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleFileUpload = async (file) => {
    // Validate file
    if (!file.name.toLowerCase().endsWith('.xml')) {
      setUploadStatus({ type: 'error', message: 'Please select an XML file' });
      if (onError) onError('Please select an XML file');
      return;
    }

    if (file.size > 50 * 1024 * 1024) { // 50MB limit
      setUploadStatus({ type: 'error', message: 'File size must be less than 50MB' });
      if (onError) onError('File size must be less than 50MB');
      return;
    }

    setUploading(true);
    setUploadStatus(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('scan_type', 'Uploaded Scan');

      const response = await fetch('/api/upload-scan', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (response.ok) {
        setUploadStatus({ 
          type: 'success', 
          message: `Upload successful! Found ${result.hosts_count} hosts and ${result.vulns_count} vulnerabilities.` 
        });
        if (onUploadComplete) {
          onUploadComplete(result);
        }
      } else {
        setUploadStatus({ type: 'error', message: result.error || 'Upload failed' });
        if (onError) onError(result.error || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      setUploadStatus({ type: 'error', message: 'Network error during upload' });
      if (onError) onError('Network error during upload');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <div
        className={`
          border-2 border-dashed rounded-lg p-8 text-center transition-colors
          ${isDragging 
            ? 'border-blue-400 bg-blue-400/10' 
            : uploading 
              ? 'border-gray-600 bg-gray-800/40' 
              : 'border-gray-600 hover:border-gray-500 hover:bg-gray-800/20'
          }
          ${uploading ? 'cursor-not-allowed' : 'cursor-pointer'}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !uploading && document.getElementById('file-input').click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".xml"
          onChange={handleFileSelect}
          className="hidden"
          disabled={uploading}
        />

        <div className="flex flex-col items-center">
          {uploading ? (
            <>
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
              <p className="text-gray-300">Uploading and parsing scan results...</p>
            </>
          ) : (
            <>
              <Upload className="h-12 w-12 text-gray-400 mb-4" />
              <p className="text-lg font-medium text-gray-100 mb-2">
                Drop your nmap XML file here
              </p>
              <p className="text-sm text-gray-400 mb-4">
                or click to browse files
              </p>
              <p className="text-xs text-gray-500">
                Supports XML files up to 50MB
              </p>
            </>
          )}
        </div>
      </div>

      {uploadStatus && (
        <div className={`
          mt-4 p-4 rounded-lg flex items-center
          ${uploadStatus.type === 'success' 
            ? 'bg-green-900/20 border border-green-700/30' 
            : 'bg-red-900/20 border border-red-700/30'
          }
        `}>
          {uploadStatus.type === 'success' ? (
            <CheckCircle className="h-5 w-5 text-green-400 mr-3 flex-shrink-0" />
          ) : (
            <AlertCircle className="h-5 w-5 text-red-400 mr-3 flex-shrink-0" />
          )}
          <p className={`text-sm ${
            uploadStatus.type === 'success' ? 'text-green-300' : 'text-red-300'
          }`}>
            {uploadStatus.message}
          </p>
        </div>
      )}

      <div className="mt-6 bg-gray-800/40 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-200 mb-2">Example nmap commands:</h4>
        <div className="space-y-2 text-sm text-gray-400 font-mono">
          <div className="bg-gray-900/60 rounded px-3 py-2">
            <div className="flex items-center mb-1">
              <FileText className="h-4 w-4 mr-2 text-blue-400" />
              <span className="font-semibold text-gray-300">Basic scan:</span>
            </div>
            <code className="text-green-400">nmap -v -T4 -sS -p- --open 192.168.1.0/24 -oX scan_output.xml</code>
          </div>
          <div className="bg-gray-900/60 rounded px-3 py-2">
            <div className="flex items-center mb-1">
              <FileText className="h-4 w-4 mr-2 text-blue-400" />
              <span className="font-semibold text-gray-300">With OS detection:</span>
            </div>
            <code className="text-green-400">nmap -v -T4 -sS -p- --open -O -sV 192.168.1.0/24 -oX scan_output.xml</code>
          </div>
          <div className="bg-gray-900/60 rounded px-3 py-2">
            <div className="flex items-center mb-1">
              <FileText className="h-4 w-4 mr-2 text-blue-400" />
              <span className="font-semibold text-gray-300">Vulnerability scan:</span>
            </div>
            <code className="text-green-400">nmap -v -T4 -sS -p- --open --script=vuln 192.168.1.0/24 -oX scan_output.xml</code>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-3">
          <strong>Tip:</strong> Always use <code className="text-blue-400">-oX filename.xml</code> to generate XML output that can be uploaded here.
        </p>
      </div>
    </div>
  );
};

export default ScanUploader;
