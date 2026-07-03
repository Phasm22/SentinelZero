import React, { useEffect, useMemo, useState } from 'react'
import { apiService } from '@/utils/api'
import { AlertTriangle, Radar } from 'lucide-react'
import HunterRunHeader from '../components/hunter/HunterRunHeader'
import HunterChangeSummary from '../components/hunter/HunterChangeSummary'
import HunterHostList from '../components/hunter/HunterHostList'
import HunterTimeline from '../components/hunter/HunterTimeline'
import HunterNarrative from '../components/hunter/HunterNarrative'
import HunterMissionStatus from '../components/hunter/HunterMissionStatus'
import HunterPivotChain from '../components/hunter/HunterPivotChain'
import InfoModalTrigger from '../components/InfoModalTrigger'
import { HunterRunsPageHelp } from '../components/hunter/hunterHelpContent'
import { deriveRunInsight } from '../components/hunter/hunterFormat'

const Card = ({ children, className = '' }) => (
  <div className={`bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-4 sm:p-6 ${className}`}>
    {children}
  </div>
)

const HunterRuns = () => {
  const [overview, setOverview] = useState(null)
  const [missions, setMissions] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    async function load() {
      try {
        setIsLoading(true)
        const payload = await apiService.getHunterOverview(30)
        const missionPayload = await apiService.getHunterMissions(20).catch(() => ({ missions: [] }))
        if (!active) return
        setOverview(payload)
        setMissions(missionPayload?.missions || [])
        setSelectedRunId(payload?.runs?.[0]?.huntRun?.runId || null)
      } catch (err) {
        if (!active) return
        setError(err?.response?.data?.error || 'Failed to load hunter runs')
      } finally {
        if (active) setIsLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [])

  const runs = overview?.runs || []
  const selectedRun = useMemo(
    () => runs.find((run) => run?.huntRun?.runId === selectedRunId) || runs[0] || null,
    [runs, selectedRunId]
  )
  const insight = useMemo(() => (selectedRun ? deriveRunInsight(selectedRun) : null), [selectedRun])

  if (isLoading) {
    return (
      <div className="p-4 sm:p-6 max-w-7xl mx-auto">
        <Card className="flex items-center justify-center gap-3">
          <div className="h-6 w-6 animate-spin rounded-full border-b-2 border-blue-400" />
          <span className="text-gray-300">Loading hunter runs…</span>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 sm:p-6 max-w-7xl mx-auto">
        <Card className="border-red-700/40 !bg-red-900/20 text-red-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        </Card>
      </div>
    )
  }

  if (!selectedRun) {
    return (
      <div className="p-4 sm:p-6 max-w-7xl mx-auto">
        <Card className="text-gray-300">No hunter runs found.</Card>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Radar className="w-6 h-6 sm:w-8 sm:h-8 text-blue-400" />
          <h1 className="text-xl sm:text-2xl font-bold text-gray-100">Hunter Runs</h1>
          <InfoModalTrigger
            title="Hunter Runs"
            ariaLabel="About Hunter runs and pivot missions"
            testId="hunter-runs-page-help"
            iconClassName="w-5 h-5"
          >
            <HunterRunsPageHelp />
          </InfoModalTrigger>
          <span className="rounded-full border border-gray-600/50 bg-gray-800/70 px-2.5 py-0.5 text-xs text-gray-300">
            {overview?.meta?.run_count || runs.length} runs
          </span>
        </div>
        <div className="text-sm text-gray-400">
          Baseline hosts: <span className="font-mono text-gray-200">{overview?.meta?.baseline_fingerprint_hosts ?? '—'}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:gap-6 xl:grid-cols-4">
        <div className="xl:col-span-1 space-y-4">
          <HunterTimeline runs={runs} selectedRunId={selectedRun.huntRun?.runId} onSelect={setSelectedRunId} />
          <HunterMissionStatus missions={missions} />
        </div>

        <section className="space-y-4 sm:space-y-6 xl:col-span-3">
          <HunterRunHeader run={selectedRun} insight={insight} />
          <HunterChangeSummary run={selectedRun} insight={insight} />
          {selectedRun.huntPivotChain && <HunterPivotChain chain={selectedRun.huntPivotChain} />}
          <HunterHostList insight={insight} />
          <HunterNarrative run={selectedRun} />
        </section>
      </div>
    </div>
  )
}

export default HunterRuns
