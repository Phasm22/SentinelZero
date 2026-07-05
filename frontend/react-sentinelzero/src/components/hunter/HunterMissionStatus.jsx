import React, { useState } from 'react'
import { Activity } from 'lucide-react'
import InfoModalTrigger from '../InfoModalTrigger'
import { PivotMissionsPanelHelp } from './hunterHelpContent'
import HunterMissionModal from './HunterMissionModal'

const STATE_STYLES = {
  running: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  done: 'bg-green-500/20 text-green-300 border-green-500/40',
  failed: 'bg-red-500/20 text-red-300 border-red-500/40',
  stalled: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  queued: 'bg-gray-500/20 text-gray-300 border-gray-500/40',
}

const HunterMissionStatus = ({ missions = [], onSelectRun }) => {
  const [selectedMissionId, setSelectedMissionId] = useState(null)

  return (
    <>
      <div className="card-glass p-4">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mb-3">
          <Activity className="w-4 h-4 text-purple-400 flex-shrink-0" />
          <h3 className="text-sm card-heading">Pivot Missions</h3>
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
          <p className="card-meta leading-relaxed">
            No pivot missions yet. Start one from Dashboard → Recent Insights → expand an escalated Lab insight.
          </p>
        ) : (
          <ul className="space-y-2">
            {missions.map((mission) => {
              const state = mission.state || 'unknown'
              return (
                <li key={mission.missionId}>
                  <button
                    type="button"
                    onClick={() => setSelectedMissionId(mission.missionId)}
                    className="w-full card-glass-item px-3 py-2 text-sm text-left hover:border-purple-400/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
                  >
                    <div className="flex flex-col gap-1.5 min-w-0">
                      <span className="font-mono text-gray-100 break-all leading-snug">
                        {mission.missionId}
                      </span>
                      <div className="flex items-center justify-between gap-2">
                        <span className={`inline-flex text-xs px-2 py-0.5 rounded border ${STATE_STYLES[state] || STATE_STYLES.queued}`}>
                          {state}
                        </span>
                        {mission.lastTask && (
                          <span className="text-xs text-gray-400">{mission.lastTask}</span>
                        )}
                      </div>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <HunterMissionModal
        missionId={selectedMissionId}
        isOpen={Boolean(selectedMissionId)}
        onClose={() => setSelectedMissionId(null)}
        onSelectRun={onSelectRun}
      />
    </>
  )
}

export default HunterMissionStatus
