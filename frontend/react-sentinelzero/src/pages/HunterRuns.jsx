import React, { useEffect, useMemo, useState } from 'react'
import { apiService } from '@/utils/api'
import { AlertTriangle, Bot, ChevronRight, Clock3, Radar, ShieldAlert } from 'lucide-react'

const PRIORITY_STYLES = {
  now: 'text-red-300 bg-red-900/30 border-red-700/50',
  next_scan: 'text-amber-300 bg-amber-900/30 border-amber-700/50',
  observe: 'text-blue-300 bg-blue-900/30 border-blue-700/50',
  none_until_online: 'text-gray-300 bg-gray-800/60 border-gray-600/50',
}

function fmtTime(ts) {
  if (!ts) return 'Unknown'
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ts
  return date.toLocaleString()
}

function CounterCard({ label, value }) {
  return (
    <div className="rounded-md border border-white/10 bg-gray-900/60 p-3">
      <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
      <div className="mt-1 text-xl font-semibold text-gray-100">{value}</div>
    </div>
  )
}

const HunterRuns = () => {
  const [overview, setOverview] = useState(null)
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    async function load() {
      try {
        setIsLoading(true)
        const payload = await apiService.getHunterOverview(30)
        if (!active) return
        setOverview(payload)
        const firstRun = payload?.runs?.[0]
        setSelectedRunId(firstRun?.huntRun?.runId || null)
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

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-primary-500" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-700/40 bg-red-900/20 p-4 text-red-200">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      </div>
    )
  }

  if (!selectedRun) {
    return (
      <div className="rounded-md border border-white/10 bg-gray-900/50 p-4 text-gray-300">
        No hunter runs found.
      </div>
    )
  }

  const runMeta = selectedRun.huntRun || {}
  const histogram = selectedRun.whatChanged?.eventHistogram || {}
  const recommendations = selectedRun.huntRecommendation || []
  const topHosts = selectedRun.huntHost || []
  const llmPack = selectedRun.llmContextPack || {}

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-white/10 bg-gray-900/50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Radar className="h-5 w-5 text-cyan-300" />
            <h2 className="text-xl font-semibold text-gray-100">Hunter Runs</h2>
            <span className="rounded border border-gray-600/50 bg-gray-800/70 px-2 py-0.5 text-xs text-gray-300">
              {overview?.meta?.run_count || runs.length} runs
            </span>
          </div>
          <div className="text-xs text-gray-400">
            Baseline hosts: {overview?.meta?.baseline_fingerprint_hosts ?? 'n/a'}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <aside className="space-y-2 xl:col-span-1">
          <div className="rounded-md border border-white/10 bg-gray-900/50 p-3 text-sm font-semibold text-gray-200">
            Run Timeline
          </div>
          <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
            {runs.map((run) => {
              const rowMeta = run.huntRun || {}
              const active = rowMeta.runId === selectedRunId
              return (
                <button
                  key={rowMeta.runId}
                  onClick={() => setSelectedRunId(rowMeta.runId)}
                  className={`w-full rounded-md border p-3 text-left transition ${
                    active
                      ? 'border-primary-500/60 bg-primary-900/20'
                      : 'border-white/10 bg-gray-900/40 hover:border-white/30'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-gray-100">{rowMeta.missionId}</div>
                    <ChevronRight className="h-4 w-4 text-gray-400" />
                  </div>
                  <div className="mt-1 text-xs text-gray-400">{rowMeta.targetNetwork}</div>
                  <div className="mt-1 text-xs text-gray-400">{fmtTime(rowMeta.completedAt)}</div>
                </button>
              )
            })}
          </div>
        </aside>

        <section className="space-y-4 xl:col-span-3">
          <div className="rounded-md border border-white/10 bg-gray-900/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-wide text-gray-400">Run Header</div>
                <div className="text-lg font-semibold text-gray-100">
                  {runMeta.missionId} · {runMeta.targetNetwork}
                </div>
                <div className="mt-1 flex items-center gap-2 text-sm text-gray-300">
                  <Clock3 className="h-4 w-4" />
                  {fmtTime(runMeta.completedAt)}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded border border-cyan-700/40 bg-cyan-900/20 px-2 py-1 text-cyan-200">
                  scan: {runMeta.scanTriggerStatus || 'none'}
                </span>
                <span className="rounded border border-gray-600/50 bg-gray-800/70 px-2 py-1 text-gray-200">
                  recommendations: {runMeta.hostsRecommendedTotal || 0}
                </span>
                {runMeta.hostsRecommendedCapped && (
                  <span className="rounded border border-amber-700/40 bg-amber-900/20 px-2 py-1 text-amber-200">
                    capped
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <CounterCard label="Event Total" value={selectedRun.whatChanged?.eventTotal || 0} />
            <CounterCard label="Hosts In Run" value={selectedRun.whatChanged?.hostTotal || 0} />
            <CounterCard label="Known Hosts" value={runMeta?.deviceContextSummary?.known ?? 'n/a'} />
            <CounterCard label="Unknown Hosts" value={runMeta?.deviceContextSummary?.unknown ?? 'n/a'} />
          </div>

          <div className="rounded-md border border-white/10 bg-gray-900/50 p-4">
            <div className="mb-3 text-sm font-semibold text-gray-200">What Changed</div>
            <div className="flex flex-wrap gap-2">
              {Object.keys(histogram).length === 0 && (
                <span className="text-sm text-gray-400">No typed events in this run.</span>
              )}
              {Object.entries(histogram).map(([type, count]) => (
                <span
                  key={type}
                  className="rounded border border-white/15 bg-gray-800/70 px-2 py-1 text-xs text-gray-200"
                >
                  {type}: {count}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-white/10 bg-gray-900/50 p-4">
            <div className="mb-3 text-sm font-semibold text-gray-200">Prioritized Hosts</div>
            <div className="space-y-2">
              {topHosts.slice(0, 8).map((host) => (
                <div key={host.ip} className="rounded-md border border-white/10 bg-gray-900/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-semibold text-gray-100">{host.ip}</div>
                    <span className={`rounded border px-2 py-0.5 text-xs ${PRIORITY_STYLES[host.actionPriority] || PRIORITY_STYLES.observe}`}>
                      {host.actionPriority}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    <span className="rounded border border-white/15 bg-gray-800/70 px-2 py-0.5 text-gray-300">novelty {host.noveltyScore}</span>
                    <span className="rounded border border-white/15 bg-gray-800/70 px-2 py-0.5 text-gray-300">drift {host.driftScore}</span>
                    <span className="rounded border border-white/15 bg-gray-800/70 px-2 py-0.5 text-gray-300">evidence {host.evidenceStrength}</span>
                    <span className="rounded border border-white/15 bg-gray-800/70 px-2 py-0.5 text-gray-300">events {host.event_count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-white/10 bg-gray-900/50 p-4">
            <div className="mb-3 text-sm font-semibold text-gray-200">Fingerprint Continuity</div>
            <div className="space-y-2 text-sm text-gray-300">
              <div>
                Baseline updates: <span className="font-semibold">{runMeta?.baselineUpdated?.count ?? 0}</span>
              </div>
              <div>
                Fingerprint events:{' '}
                <span className="font-semibold">
                  {Object.entries(histogram)
                    .filter(([type]) => ['new_device', 'new_udp_port', 'lost_udp_port', 'expected_udp_violation'].includes(type))
                    .map(([type, count]) => `${type}:${count}`)
                    .join(', ') || 'none'}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-md border border-white/10 bg-gray-900/50 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-200">
              <ShieldAlert className="h-4 w-4 text-cyan-300" />
              Narrative Panel
            </div>
            <ul className="space-y-1 text-sm text-gray-300">
              {(selectedRun.deterministicNarrative || []).map((line, idx) => (
                <li key={idx}>- {line}</li>
              ))}
            </ul>
            <div className="mt-4 rounded-md border border-white/10 bg-gray-900/70 p-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <Bot className="h-3.5 w-3.5" />
                LLM Context Pack (optional)
              </div>
              <div className="text-xs text-gray-300">
                Must mention: {(llmPack.must_mention_facts || []).join(' · ') || 'n/a'}
              </div>
              <div className="mt-2 text-xs text-gray-400">
                Acceptance checks: {(llmPack.prompt_contract?.acceptance_checks || []).join(' | ') || 'n/a'}
              </div>
            </div>
            {recommendations.length > 0 && (
              <div className="mt-3 text-xs text-gray-400">
                Top recommendations:{' '}
                {recommendations
                  .slice(0, 5)
                  .map((item) => `${item.ip}(${item.actionPriority})`)
                  .join(', ')}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

export default HunterRuns
