import React from 'react'
import { Bot } from 'lucide-react'

const ScanInsightBadge = ({ scan }) => {
  const count = scan.insights_count ?? 0
  const escalated = scan.insights_escalated ?? 0
  const agentStatus = scan.verdict_agent_status || 'not_run'

  if (count === 0 && agentStatus === 'not_run') {
    return <span className="text-xs text-gray-500">—</span>
  }

  return (
    <div className="flex flex-col gap-0.5 items-start">
      <span className="inline-flex items-center gap-1 text-xs text-violet-300">
        <Bot className="w-3 h-3" />
        {count} insight{count !== 1 ? 's' : ''}
        {escalated > 0 && (
          <span className="text-red-400">({escalated}↑)</span>
        )}
      </span>
      {agentStatus !== 'not_run' && (
        <span className={`text-xs capitalize ${
          agentStatus === 'success' ? 'text-green-400' :
          agentStatus === 'skipped' ? 'text-yellow-500' : 'text-red-400'
        }`}>
          agent: {agentStatus}
        </span>
      )}
    </div>
  )
}

export default ScanInsightBadge
