import React from 'react'
import { AlertTriangle, CheckCircle, Info, ShieldAlert } from 'lucide-react'
import LabPanel from './LabPanel'

const severityStyles = {
  critical: {
    icon: ShieldAlert,
    dot: 'bg-red-400',
    text: 'text-red-300',
    border: 'border-red-500/30',
    bg: 'bg-red-500/10',
  },
  high: {
    icon: AlertTriangle,
    dot: 'bg-orange-400',
    text: 'text-orange-300',
    border: 'border-orange-500/30',
    bg: 'bg-orange-500/10',
  },
  warning: {
    icon: AlertTriangle,
    dot: 'bg-yellow-400',
    text: 'text-yellow-300',
    border: 'border-yellow-500/30',
    bg: 'bg-yellow-500/10',
  },
  info: {
    icon: Info,
    dot: 'bg-blue-400',
    text: 'text-blue-300',
    border: 'border-blue-500/30',
    bg: 'bg-blue-500/10',
  },
}

const AttentionList = ({ items = [] }) => {
  const visibleItems = Array.isArray(items) ? items.slice(0, 8) : []

  return (
    <LabPanel className="!p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="card-heading text-base">Needs Attention</h2>
          <p className="card-meta">Prioritized lab signals from sensors and reachability checks</p>
        </div>
        <span className="card-meta font-mono">{visibleItems.length}</span>
      </div>

      {visibleItems.length === 0 ? (
        <div className="flex items-center gap-2 rounded-md border border-green-500/20 bg-green-500/10 px-3 py-2 text-sm text-green-300">
          <CheckCircle className="h-4 w-4 shrink-0" />
          <span>No current attention items</span>
        </div>
      ) : (
        <div className="space-y-2">
          {visibleItems.map((item, index) => {
            const severity = item.severity || item.status || 'info'
            const style = severityStyles[severity] || severityStyles.info
            const Icon = style.icon

            return (
              <div
                key={`${item.source || 'item'}-${item.title || index}-${index}`}
                className={`rounded-md border px-3 py-2 ${style.border} ${style.bg}`}
              >
                <div className="flex items-start gap-2">
                  <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${style.text}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-gray-100">
                        {item.title || 'Attention item'}
                      </span>
                      <span className={`rounded px-1.5 py-0.5 text-xs font-mono uppercase ${style.text} bg-black/20`}>
                        {severity}
                      </span>
                    </div>
                    {item.message && (
                      <p className="mt-1 text-xs leading-5 text-gray-300">{item.message}</p>
                    )}
                    {item.source && (
                      <div className="mt-1 text-xs font-mono text-gray-500">{item.source}</div>
                    )}
                  </div>
                  <span className={`mt-1 h-2 w-2 rounded-full ${style.dot}`} />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </LabPanel>
  )
}

export default AttentionList
