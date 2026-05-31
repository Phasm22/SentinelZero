import React from 'react'
import { ShieldAlert } from 'lucide-react'
import { actionTier } from './hunterFormat'

const HunterNarrative = ({ run }) => {
  const bullets = run.deterministicNarrative || []
  const recommendations = (run.huntRecommendation || []).slice(0, 5)

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-4 sm:p-6">
      <div className="flex items-center gap-3 mb-4">
        <ShieldAlert className="w-5 h-5 sm:w-6 sm:h-6 text-blue-400" />
        <h3 className="text-lg sm:text-xl font-bold text-gray-200">Summary</h3>
      </div>

      <ul className="space-y-2">
        {bullets.map((line, idx) => (
          <li key={idx} className="flex gap-2.5 text-sm text-gray-300">
            <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-400/80 flex-shrink-0" />
            <span>{line}</span>
          </li>
        ))}
      </ul>

      {recommendations.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-600/30">
          <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">Top recommendations</div>
          <div className="flex flex-wrap gap-2">
            {recommendations.map((item) => {
              const tier = actionTier(item.actionPriority)
              return (
                <span
                  key={item.ip}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${tier.bg} ${tier.border} ${tier.text}`}
                >
                  <span className="font-mono">{item.ip}</span>
                  <span className="opacity-80">{tier.label}</span>
                </span>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default HunterNarrative
