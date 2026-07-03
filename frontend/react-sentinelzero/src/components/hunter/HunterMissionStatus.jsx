import React from 'react'
import { Activity } from 'lucide-react'
import InfoModalTrigger from '../InfoModalTrigger'
import { PivotMissionsPanelHelp } from './hunterHelpContent'

const STATE_STYLES = {
  running: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  done: 'bg-green-500/20 text-green-300 border-green-500/40',
  failed: 'bg-red-500/20 text-red-300 border-red-500/40',
  stalled: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  queued: 'bg-gray-500/20 text-gray-300 border-gray-500/40',
}

const HunterMissionStatus = ({ missions = [] }) => (
  <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 rounded-md shadow-xl p-4">
    <div className="flex items-center gap-2 mb-3">
      <Activity className="w-4 h-4 text-purple-400 flex-shrink-0" />
      <h3 className="text-sm font-semibold text-gray-200">Pivot Missions</h3>
      <InfoModalTrigger
        title="Pivot Mission Status"
        ariaLabel="Pivot mission status meanings"
        testId="pivot-missions-help"
        iconClassName="w-3.5 h-3.5"
      >
        <PivotMissionsPanelHelp />
      </InfoModalTrigger>
      {missions.length > 0 && (
        <span className="ml-auto text-xs text-gray-400 font-mono">{missions.length}</span>
      )}
    </div>

    {missions.length === 0 ? (
      <p className="text-xs text-gray-500 leading-relaxed">
        No pivot missions yet. Start one from Dashboard → Recent Insights → expand an escalated Lab insight.
      </p>
    ) : (
      <ul className="space-y-2">
        {missions.map((mission) => {
          const state = mission.state || 'unknown'
          return (
            <li
              key={mission.missionId}
              className="rounded-lg border border-white/10 bg-gray-900/40 px-3 py-2 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-gray-100 truncate">{mission.missionId}</span>
                <span className={`text-xs px-2 py-0.5 rounded border ${STATE_STYLES[state] || STATE_STYLES.queued}`}>
                  {state}
                </span>
              </div>
              {mission.lastTask && (
                <p className="text-xs text-gray-400 mt-1 truncate">{mission.lastTask}</p>
              )}
            </li>
          )
        })}
      </ul>
    )}
  </div>
)

export default HunterMissionStatus
