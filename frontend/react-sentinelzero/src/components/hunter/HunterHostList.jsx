import React, { useState } from 'react'
import { Crosshair, ChevronDown, ChevronRight } from 'lucide-react'
import PrioritizedHostCard from './PrioritizedHostCard'
import { actionTier } from './hunterFormat'

const DISTRIBUTION_ORDER = ['now', 'next_scan', 'observe', 'none_until_online']

const HunterHostList = ({ insight }) => {
  const { signalHosts, quietHosts, actionCounts } = insight
  const [showQuiet, setShowQuiet] = useState(false)

  const quietPriority = quietHosts[0]?.actionPriority || 'next_scan'
  const quietTier = actionTier(quietPriority)

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-4 sm:p-6">
      <div className="flex items-center gap-3 mb-4">
        <Crosshair className="w-5 h-5 sm:w-6 sm:h-6 text-blue-400" />
        <h3 className="text-lg sm:text-xl font-bold text-gray-200">Prioritized Hosts</h3>
        <div className="ml-auto flex flex-wrap gap-2">
          {DISTRIBUTION_ORDER.filter((p) => (actionCounts[p] || 0) > 0).map((p) => {
            const tier = actionTier(p)
            return (
              <span key={p} className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-xs ${tier.bg} ${tier.border} ${tier.text}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${tier.dot}`} />
                {tier.label} <span className="font-mono opacity-80">{actionCounts[p]}</span>
              </span>
            )
          })}
        </div>
      </div>

      <div className="space-y-2">
        {signalHosts.length === 0 && quietHosts.length === 0 && (
          <p className="text-sm text-gray-400">No hosts in this run.</p>
        )}

        {signalHosts.map((host) => (
          <PrioritizedHostCard key={host.ip} host={host} />
        ))}

        {quietHosts.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => setShowQuiet((v) => !v)}
              className="w-full flex items-center justify-between gap-3 rounded-lg border border-gray-600/30 bg-gray-700/30 hover:bg-gray-700/50 px-4 py-3 transition-colors"
            >
              <span className="flex items-center gap-2 text-sm text-gray-200">
                <span className={`w-2 h-2 rounded-full ${quietTier.dot}`} />
                {quietHosts.length} host{quietHosts.length === 1 ? '' : 's'} {quietTier.label.toLowerCase()} · no anomalies
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-400">
                {showQuiet ? 'Hide' : 'Show all'}
                {showQuiet ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </span>
            </button>
            {showQuiet && (
              <div className="space-y-2 pl-1">
                {quietHosts.map((host) => (
                  <PrioritizedHostCard key={host.ip} host={host} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default HunterHostList
