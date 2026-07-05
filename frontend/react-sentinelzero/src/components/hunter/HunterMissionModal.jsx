import React, { useEffect, useState } from 'react'
import { Activity, ExternalLink } from 'lucide-react'
import Modal from '../Modal'
import Button from '../Button'
import { apiService } from '@/utils/api'
import { fmtTime } from './hunterFormat'

const STATE_STYLES = {
  running: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  done: 'bg-green-500/20 text-green-300 border-green-500/40',
  failed: 'bg-red-500/20 text-red-300 border-red-500/40',
  stalled: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  queued: 'bg-gray-500/20 text-gray-300 border-gray-500/40',
}

const HunterMissionModal = ({ missionId, isOpen, onClose, onSelectRun }) => {
  const [mission, setMission] = useState(null)
  const [log, setLog] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isOpen || !missionId) {
      setMission(null)
      setLog('')
      setError('')
      return undefined
    }

    let active = true
    async function load() {
      setIsLoading(true)
      setError('')
      try {
        const [detail, logPayload] = await Promise.all([
          apiService.getHunterMission(missionId),
          apiService.getHunterMissionLog(missionId).catch(() => ({ log: '' })),
        ])
        if (!active) return
        setMission(detail?.mission || null)
        setLog(logPayload?.log || '')
      } catch (err) {
        if (!active) return
        setError(err?.response?.data?.error || 'Failed to load pivot mission')
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [isOpen, missionId])

  const state = mission?.state || 'unknown'
  const reportId = mission?.reportId

  const handleViewRun = () => {
    if (!reportId || !onSelectRun) return
    onSelectRun(reportId)
    onClose()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Pivot Mission" size="xl">
      {isLoading ? (
        <div className="flex items-center gap-3 text-gray-300">
          <div className="h-5 w-5 animate-spin rounded-full border-b-2 border-blue-400" />
          Loading mission…
        </div>
      ) : error ? (
        <p className="text-sm text-red-300">{error}</p>
      ) : (
        <div className="space-y-4 text-gray-300">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm">
                <Activity className="w-4 h-4 text-purple-400" />
                <span className={`text-xs px-2 py-0.5 rounded border ${STATE_STYLES[state] || STATE_STYLES.queued}`}>
                  {state}
                </span>
              </div>
              <p className="mt-2 font-mono text-sm text-gray-100 break-all">{missionId}</p>
              {mission?.lastTask && (
                <p className="mt-1 text-xs text-gray-400">{mission.lastTask}</p>
              )}
              {mission?.startedAt && (
                <p className="mt-1 text-xs text-gray-400">Started {fmtTime(mission.startedAt)}</p>
              )}
              {mission?.host && (
                <p className="mt-1 text-xs text-gray-400 font-mono">
                  {mission.host}{mission.type ? ` · ${mission.type.replace(/_/g, ' ')}` : ''}
                </p>
              )}
            </div>
            {reportId && (
              <Button variant="outline" size="sm" onClick={handleViewRun} icon={<ExternalLink className="w-4 h-4" />}>
                View run
              </Button>
            )}
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-wide text-gray-400 mb-2">Mission log</h4>
            <pre className="max-h-[50vh] overflow-auto rounded-lg border border-gray-600 bg-gray-900/60 p-3 text-xs font-mono text-gray-200 whitespace-pre-wrap break-words">
              {log || 'No log output yet.'}
            </pre>
          </div>
        </div>
      )}
    </Modal>
  )
}

export default HunterMissionModal
