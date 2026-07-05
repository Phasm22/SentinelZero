import React from 'react'

const StatCard = ({ icon, label, value, valueClass = '', hoverRing = '', ...props }) => (
  <div className={`card-glass p-6 flex flex-col items-center gap-2 transition-all duration-200 hover:shadow-2xl hover:ring-2 ${hoverRing} hover:scale-105`} data-testid={props['data-testid'] || 'stat-card'}>
    <div data-testid="stat-icon">{icon}</div>
    <div className="text-base text-gray-300" data-testid="stat-label">{label}</div>
    <div className={`text-gray-100 ${valueClass}`} data-testid="stat-value">{value}</div>
  </div>
)

export default StatCard
