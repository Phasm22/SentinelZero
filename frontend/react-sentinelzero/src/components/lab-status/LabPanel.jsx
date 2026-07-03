import React from 'react'

const LabPanel = ({ children, className = '' }) => (
  <div
    className={`bg-gradient-to-br from-white/95 to-gray-50/90 dark:from-gray-800/80 dark:to-gray-900/60 backdrop-blur-lg border border-gray-200/80 dark:border-white/10 rounded-md shadow-xl p-4 sm:p-6 ${className}`}
  >
    {children}
  </div>
)

export default LabPanel
