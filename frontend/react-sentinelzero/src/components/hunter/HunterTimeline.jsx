import React from 'react'
import { Radar } from 'lucide-react'
import { scanStatusMeta } from './hunterFormat'
import { runTimeLabel } from './hunterTimeFilter'

const STATUS_DOT = {
  healthy: 'bg-green-400 shadow-green-400/50',
  critical: 'bg-red-400 shadow-red-400/50',
  unknown: 'bg-gray-500',
}

const HunterTimeline = ({ runs, selectedRunId, onSelect }) => (
  <aside className="space-y-2">
    <div className="card-glass px-4 py-3 flex items-center gap-2">
      <Radar className="w-4 h-4 text-blue-400" />
      <span className="text-sm card-heading">Run Timeline</span>
      <span className="ml-auto text-xs text-gray-400 font-mono">{runs.length}</span>
    </div>

    <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
      {runs.map((run) => {
        const meta = run.huntRun || {}
        const active = meta.runId === selectedRunId
        const scan = scanStatusMeta(meta.scanTriggerStatus)
        const eventCount = run.whatChanged?.eventTotal || 0
        const missionLabel = meta.missionId || 'run'
        const typeLabel = meta.missionType && meta.missionType !== 'inventory'
          ? meta.missionType.replace(/_/g, ' ')
          : null
        return (
          <button
            key={meta.runId}
            type="button"
            onClick={() => onSelect(meta.runId)}
            aria-pressed={active}
            className={`w-full text-left rounded-lg border p-3 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 ${
              active
                ? 'card-glass-item-active'
                : 'card-glass-item'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 min-w-0">
                <span className={`w-2 h-2 rounded-full shadow-sm flex-shrink-0 ${STATUS_DOT[scan.status]}`} title={scan.label} />
                <span className="text-sm font-semibold text-gray-100 break-all leading-snug">{missionLabel}</span>
              </span>
              {eventCount > 0 ? (
                <span className="flex-shrink-0 rounded-full bg-blue-500/20 border border-blue-500/30 px-2 py-0.5 text-[10px] font-mono text-blue-300">
                  {eventCount}
                </span>
              ) : (
                <span className="flex-shrink-0 text-[10px] font-mono text-gray-500">—</span>
              )}
            </div>
            <div className="mt-1 text-xs text-gray-400 font-mono break-all">{meta.targetNetwork}</div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
              <span>{runTimeLabel(meta)}</span>
              {typeLabel && <span className="capitalize">{typeLabel}</span>}
            </div>
          </button>
        )
      })}
    </div>
  </aside>
)

export default HunterTimeline
