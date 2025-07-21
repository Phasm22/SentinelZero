import React from 'react'
import { AlertTriangle, PlusCircle, ShieldCheck } from 'lucide-react'

const mockInsights = [
  {
    type: 'port',
    host: '10.0.0.5',
    port: 8080,
    status: 'new',
    time: '2024-07-20T12:34:00Z',
  },
  {
    type: 'vuln',
    host: '10.0.0.7',
    vuln: 'CVE-2024-1234',
    status: 'new',
    time: '2024-07-20T12:35:00Z',
  },
  {
    type: 'vuln',
    host: '10.0.0.8',
    vuln: 'CVE-2023-9999',
    status: 'resolved',
    time: '2024-07-20T12:36:00Z',
  },
]

const formatTime = (iso) => new Date(iso).toLocaleString()

const InsightsCard = () => (
  <div className="bg-gradient-to-br from-green-900/80 to-gray-900/60 border border-green-400/30 rounded-2xl shadow-xl p-6 mb-8" data-testid="insights-card">
    <h2 className="text-2xl font-title font-bold text-green-200 mb-4 flex items-center gap-2">
      <PlusCircle className="w-6 h-6 text-green-400" /> Recent Insights
    </h2>
    <ul className="space-y-3">
      {mockInsights.map((insight, idx) => (
        <li key={idx} className="flex items-center gap-3 p-3 rounded-lg bg-white/5" data-testid={`insight-row-${idx}`}>
          {insight.type === 'port' && (
            <PlusCircle className="w-5 h-5 text-blue-400" />
          )}
          {insight.type === 'vuln' && insight.status === 'new' && (
            <AlertTriangle className="w-5 h-5 text-red-400 animate-pulse" />
          )}
          {insight.type === 'vuln' && insight.status === 'resolved' && (
            <ShieldCheck className="w-5 h-5 text-green-400" />
          )}
          <span className="font-mono text-sm text-gray-200">
            {insight.type === 'port' && (
              <>
                <span className="font-bold text-blue-300">{insight.host}</span>: New port <span className="font-bold text-blue-400">{insight.port}</span> open
              </>
            )}
            {insight.type === 'vuln' && insight.status === 'new' && (
              <>
                <span className="font-bold text-red-300">{insight.host}</span>: New vulnerability <span className="font-bold text-red-400">{insight.vuln}</span> detected
              </>
            )}
            {insight.type === 'vuln' && insight.status === 'resolved' && (
              <>
                <span className="font-bold text-green-300">{insight.host}</span>: Vulnerability <span className="font-bold text-green-400">{insight.vuln}</span> resolved
              </>
            )}
          </span>
          <span className="ml-auto text-xs text-gray-400">{formatTime(insight.time)}</span>
        </li>
      ))}
    </ul>
  </div>
)

export default InsightsCard 