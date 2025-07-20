import React from 'react'

const StatCard = ({ icon, label, value, valueClass = '', hoverRing = '' }) => (
  <div className={`bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-2xl shadow-xl p-6 flex flex-col items-center gap-2 transition-all duration-200 hover:shadow-2xl hover:ring-2 ${hoverRing} hover:scale-105`}>
    {icon}
    <div className="text-base text-gray-300">{label}</div>
    <div className={valueClass}>{value}</div>
  </div>
)

export default StatCard 