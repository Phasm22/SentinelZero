import React from 'react'

const LabPanel = ({ children, className = '' }) => (
  <div
    className={`card-glass p-4 sm:p-6 ${className}`}
  >
    {children}
  </div>
)

export default LabPanel
