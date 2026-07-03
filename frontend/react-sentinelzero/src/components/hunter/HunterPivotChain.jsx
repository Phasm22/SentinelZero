import React from 'react'
import { GitBranch } from 'lucide-react'

const HunterPivotChain = ({ chain }) => {
  const events = chain?.events || []
  if (!events.length) return null

  return (
    <div className="bg-gradient-to-br from-white/95 to-gray-50/90 dark:from-gray-800/80 dark:to-gray-900/60 backdrop-blur-lg border border-gray-200/80 dark:border-white/10 rounded-md shadow-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-cyan-400" />
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200">Pivot Chain</h3>
        <span className="ml-auto text-xs text-gray-500 dark:text-gray-400 font-mono">
          {chain.eventTotal} events · depth {chain.depth}
        </span>
      </div>
      <ol className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {events.map((event) => (
          <li
            key={event.eventId}
            className="rounded border border-white/10 bg-gray-900/50 px-3 py-2 text-xs"
          >
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-300">
              <span className="font-mono text-cyan-300/90">#{event.seq}</span>
              <span className="font-semibold text-gray-900 dark:text-gray-100">{event.type}</span>
              {event.ip && <span className="font-mono text-gray-500 dark:text-gray-400">{event.ip}</span>}
            </div>
            <p className="text-gray-500 dark:text-gray-400 mt-1">{event.description}</p>
            {event.parentEventId && (
              <p className="text-gray-500 mt-1 font-mono">↳ parent {event.parentEventId}</p>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}

export default HunterPivotChain
