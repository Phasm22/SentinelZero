import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Cpu } from 'lucide-react'
import { actionTier, severityTier, classifyHost, hostPorts, friendlyService } from './hunterFormat'

const Metric = ({ label, value, highlight }) => (
  <div className="flex flex-col items-end min-w-[2.75rem]">
    <span className="text-[9px] uppercase tracking-wider text-gray-500 leading-none">{label}</span>
    <span className={`mt-0.5 text-sm font-mono leading-none ${highlight && value > 0 ? 'text-gray-900 dark:text-gray-100 font-semibold' : 'text-gray-500 dark:text-gray-400'}`}>{value}</span>
  </div>
)

const PortChip = ({ port }) => (
  <span className="inline-flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-800/70 border border-gray-200 dark:border-white/10 px-1.5 py-0.5 text-[10px] font-mono text-gray-600 dark:text-gray-300">
    <span className="text-gray-500">{port.protocol}/{port.port}</span>
    {port.service && <span className="text-cyan-300">{friendlyService(port.service)}</span>}
  </span>
)

// Dedup repeated event descriptions (the same finding is emitted per port).
function uniqueEvents(events = []) {
  const seen = new Set()
  const out = []
  for (const ev of events) {
    const key = ev.description || `${ev.type}:${ev.event_id}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(ev)
  }
  return out
}

const PrioritizedHostCard = ({ host }) => {
  const [expanded, setExpanded] = useState(false)
  const tier = actionTier(host.actionPriority)
  const classification = classifyHost(host)
  const ports = hostPorts(host)
  const events = uniqueEvents(host.events)

  return (
    <div
      className={`group bg-gradient-to-br from-white/95 to-gray-50/90 dark:from-gray-800/90 dark:to-gray-900/70 backdrop-blur-xl border border-gray-200/80 dark:border-white/10 border-l-4 ${tier.accent} rounded-lg shadow-lg transition-all duration-300 hover:shadow-2xl`}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className={`w-full text-left p-3 sm:p-4 cursor-pointer rounded-lg transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 ${
          expanded
            ? 'bg-blue-500/10 ring-1 ring-blue-500/30'
            : 'hover:bg-white/[0.06] active:bg-white/[0.08]'
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <span className="font-mono font-bold text-gray-50 text-base sm:text-lg tracking-tight flex-shrink-0">{host.ip}</span>
            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[11px] font-medium whitespace-nowrap flex-shrink-0 ${tier.bg} ${tier.border} ${tier.text}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${tier.dot}`} />
              {tier.label}
            </span>
            <span className="hidden sm:inline-flex items-center gap-1 text-xs text-cyan-300/80 min-w-0">
              <Cpu className="w-3.5 h-3.5 flex-shrink-0" />
              <span className="truncate">{classification.label}</span>
            </span>
          </div>
          <div className="flex items-center gap-3 sm:gap-4 flex-shrink-0">
            <div className="hidden sm:flex items-center gap-3 sm:gap-4">
              <Metric label="Novelty" value={host.noveltyScore} highlight />
              <Metric label="Drift" value={host.driftScore} highlight />
              <Metric label="Evidence" value={host.evidenceStrength} />
              <Metric label="Events" value={host.event_count} highlight />
            </div>
            {expanded ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-blue-500/30 bg-blue-500/15 px-2 py-1 text-xs text-blue-200 flex-shrink-0">
                Hide
                <ChevronDown className="w-4 h-4" />
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-md border border-gray-600/40 bg-gray-700/50 px-2 py-1 text-xs text-gray-500 dark:text-gray-400 flex-shrink-0 transition-colors group-hover:border-gray-500/60 group-hover:bg-gray-600/50 group-hover:text-gray-700 dark:text-gray-200">
                Details
                <ChevronRight className="w-4 h-4" />
              </span>
            )}
          </div>
        </div>
        {/* device guess + metrics for small screens */}
        <div className="sm:hidden mt-2 space-y-2">
          <span className="inline-flex items-center gap-1 text-xs text-cyan-300/90">
            <Cpu className="w-3.5 h-3.5" />
            {classification.label}
          </span>
          <div className="flex items-center gap-4">
            <Metric label="Novelty" value={host.noveltyScore} highlight />
            <Metric label="Drift" value={host.driftScore} highlight />
            <Metric label="Evidence" value={host.evidenceStrength} />
            <Metric label="Events" value={host.event_count} highlight />
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-700/50 p-3 sm:p-4 space-y-4">
          {/* Plain-English assessment */}
          <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-3">
            <div className="flex items-center gap-2 mb-1">
              <Cpu className="w-4 h-4 text-cyan-300" />
              <span className="text-sm font-semibold text-cyan-200">Looks like: {classification.label}</span>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-300">{classification.summary}</p>
            {ports.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {ports.map((p) => (
                  <PortChip key={`${p.protocol}/${p.port}`} port={p} />
                ))}
              </div>
            )}
          </div>

          {/* Evidence */}
          {events.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Evidence</div>
              {events.map((event) => {
                const sev = severityTier(event.severity)
                return (
                  <div key={event.event_id} className="flex gap-2.5 text-sm">
                    <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${sev.dot}`} title={`${sev.label} severity`} />
                    <div className="min-w-0">
                      <span className={`text-xs font-medium ${sev.text}`}>{event.type.replace(/_/g, ' ')}</span>
                      {event.confidence && (
                        <span className="ml-2 text-[10px] uppercase tracking-wide text-gray-500">{event.confidence} conf</span>
                      )}
                      {event.description && (
                        <p className="text-gray-600 dark:text-gray-300 text-xs mt-0.5 break-words">{event.description}</p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-xs text-gray-500 dark:text-gray-400">Queued for next scan — no anomalies recorded yet.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default PrioritizedHostCard
