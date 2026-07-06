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
import {
  TIME_RANGE_OPTIONS,
  filterMissionsByTimeRange,
  filterRunsByTimeRange,
} from '../components/hunter/hunterTimeFilter'

const Card = ({ children, className = '' }) => (
  <div className={`card-glass p-4 sm:p-6 ${className}`}>
    {children}
  </div>
)

const HunterRuns = () => {
  const [overview, setOverview] = useState(null)
  const [missions, setMissions] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [timeRange, setTimeRange] = useState('7d')
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

  const allRuns = overview?.runs || []
  const filteredRuns = useMemo(
    () => filterRunsByTimeRange(allRuns, timeRange),
    [allRuns, timeRange]
  )
  const filteredMissions = useMemo(
    () => filterMissionsByTimeRange(missions, timeRange),
    [missions, timeRange]
  )

  useEffect(() => {
    if (!filteredRuns.length) {
      setSelectedRunId(null)
      return
    }
    const stillVisible = filteredRuns.some((run) => run?.huntRun?.runId === selectedRunId)
    if (!stillVisible) {
      setSelectedRunId(filteredRuns[0]?.huntRun?.runId || null)
    }
  }, [filteredRuns, selectedRunId])

  const selectedRun = useMemo(
    () => filteredRuns.find((run) => run?.huntRun?.runId === selectedRunId) || filteredRuns[0] || null,
    [filteredRuns, selectedRunId]
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
        <Card className="border-red-500/30 !bg-red-900/20 text-red-300">
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
      <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Radar className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600 dark:text-blue-400" />
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">Hunter Runs</h1>
          </div>
          <label className="flex items-center gap-2 card-label">
            <span className="card-meta uppercase tracking-wide">Show</span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="rounded border border-gray-600 bg-gray-700 px-2 py-1 text-sm text-gray-100"
            >
              {TIME_RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
        </div>
        <Card className="text-gray-300">
          No hunter runs found for the selected time range.
        </Card>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Radar className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600 dark:text-blue-400" />
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">Hunter Runs</h1>
          <InfoModalTrigger
            title="Hunter Runs"
            ariaLabel="About Hunter runs and pivot missions"
            testId="hunter-runs-page-help"
            iconClassName="w-5 h-5"
          >
            <HunterRunsPageHelp />
          </InfoModalTrigger>
          <span className="rounded-full border border-gray-600/50 bg-gray-800/70 px-2.5 py-0.5 text-xs text-gray-300">
            {filteredRuns.length} runs
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 card-label">
            <span className="card-meta uppercase tracking-wide">Show</span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="rounded border border-gray-600 bg-gray-700 px-2 py-1 text-sm text-gray-100"
            >
              {TIME_RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <div className="card-body">
            Baseline hosts: <span className="font-mono text-gray-200">{overview?.meta?.baseline_fingerprint_hosts ?? '—'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:gap-6 xl:grid-cols-4">
        <div className="xl:col-span-1 space-y-4">
          <HunterTimeline runs={filteredRuns} selectedRunId={selectedRun.huntRun?.runId} onSelect={setSelectedRunId} />
          <HunterMissionStatus missions={filteredMissions} onSelectRun={setSelectedRunId} />
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
