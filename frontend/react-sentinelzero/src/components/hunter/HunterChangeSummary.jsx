import React from 'react'
import { GitCompare, Fingerprint } from 'lucide-react'
import { SEVERITY_TIERS, severityTier, typeSeverity, sortedHistogram } from './hunterFormat'

const SEVERITY_ORDER = ['high', 'medium', 'low', 'info']

const HunterChangeSummary = ({ run, insight }) => {
  const histogram = run.whatChanged?.eventHistogram || {}
  const entries = sortedHistogram(histogram)
  const total = run.whatChanged?.eventTotal || 0
  const { severityCounts, baselineUpdates, fingerprintEvents } = insight

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-4 sm:p-6">
      <div className="flex items-center gap-3 mb-4">
        <GitCompare className="w-5 h-5 sm:w-6 sm:h-6 text-blue-400" />
        <h3 className="text-lg sm:text-xl font-bold text-gray-200">What Changed</h3>
        {total > 0 && (
          <span className="ml-auto text-sm text-gray-400 font-mono">{total} events</span>
        )}
      </div>

      {total === 0 ? (
        <div className="rounded-lg border border-gray-600/30 bg-gray-700/30 px-4 py-3 text-sm text-gray-300">
          No fingerprint changes — inventory / recon sweep only.
        </div>
      ) : (
        <>
          {/* Severity composition bar */}
          <div className="flex gap-1 mb-3">
            {SEVERITY_ORDER.flatMap((sev) => {
              const count = severityCounts[sev] || 0
              return Array.from({ length: count }).map((_, i) => (
                <div
                  key={`${sev}-${i}`}
                  className={`h-2 flex-1 rounded-full bg-gradient-to-t ${SEVERITY_TIERS[sev].bar} shadow-sm`}
                  title={`${SEVERITY_TIERS[sev].label} severity`}
                />
              ))
            })}
          </div>

          {/* Severity legend */}
          <div className="flex flex-wrap gap-3 mb-4">
            {SEVERITY_ORDER.filter((sev) => (severityCounts[sev] || 0) > 0).map((sev) => (
              <div key={sev} className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${SEVERITY_TIERS[sev].dot}`} />
                <span className="text-xs text-gray-300">{SEVERITY_TIERS[sev].label}</span>
                <span className={`text-xs font-mono ${SEVERITY_TIERS[sev].text}`}>{severityCounts[sev]}</span>
              </div>
            ))}
          </div>

          {/* Event type chips, colored + sorted by severity */}
          <div className="flex flex-wrap gap-2">
            {entries.map(([type, count]) => {
              const tier = severityTier(typeSeverity(type))
              return (
                <span
                  key={type}
                  className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs ${tier.bg} ${tier.border} ${tier.text}`}
                >
                  <span className="font-medium">{type.replace(/_/g, ' ')}</span>
                  <span className="font-mono opacity-80">{count}</span>
                </span>
              )
            })}
          </div>
        </>
      )}

      {/* Fingerprint continuity footer */}
      <div className="mt-4 pt-4 border-t border-gray-600/30 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <span className="inline-flex items-center gap-2 text-gray-300">
          <Fingerprint className="w-4 h-4 text-cyan-400" />
          Baseline updates
          <span className="font-mono text-gray-100">{baselineUpdates}</span>
        </span>
        {fingerprintEvents.length > 0 ? (
          <span className="flex flex-wrap gap-2">
            {fingerprintEvents.map(([type, count]) => {
              const tier = severityTier(typeSeverity(type))
              return (
                <span key={type} className={`inline-flex items-center gap-1 text-xs ${tier.text}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${tier.dot}`} />
                  {type.replace(/_/g, ' ')} <span className="font-mono opacity-80">{count}</span>
                </span>
              )
            })}
          </span>
        ) : (
          <span className="text-xs text-gray-500">no fingerprint drift</span>
        )}
      </div>
    </div>
  )
}

export default HunterChangeSummary
