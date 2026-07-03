import React, { useState, useEffect } from 'react'
import { Bot, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react'
import { apiService } from '../utils/api'

const VERDICT_STYLES = {
  escalate: 'text-red-700 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-900/30 dark:border-red-500/40',
  explain:  'text-green-700 bg-green-50 border-green-200 dark:text-green-400 dark:bg-green-900/30 dark:border-green-500/40',
  dismiss:  'text-gray-700 bg-gray-100 border-gray-200 dark:text-gray-400 dark:bg-gray-900/30 dark:border-gray-500/40',
}

const statusIcon = (status) => {
  switch (status) {
    case 'success': return <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
    case 'failed':
    case 'timeout': return <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
    case 'skipped': return <Clock className="w-4 h-4 text-yellow-600 dark:text-yellow-400" />
    default: return <Bot className="w-4 h-4 text-gray-500 dark:text-gray-400" />
  }
}

const ScanAiTab = ({ scanId, scanDetails }) => {
  const [insights, setInsights] = useState([])
  const [analysis, setAnalysis] = useState(scanDetails?.analysis || {})
  const [summary, setSummary] = useState({})
  const [loading, setLoading] = useState(true)
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    if (!scanId) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const data = await apiService.getScanInsights(scanId)
        if (cancelled) return
        setInsights(data.insights || [])
        setAnalysis(data.analysis || scanDetails?.analysis || {})
        setSummary(data.summary || {})
      } catch (e) {
        console.error('Scan AI tab load failed:', e)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [scanId, scanDetails?.analysis])

  if (loading) {
    return (
      <div className="flex justify-center py-10">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500" />
      </div>
    )
  }

  const ig = analysis.insights_generation || {}
  const va = analysis.verdict_agent || {}
  const syn = analysis.synthesis_agent || {}
  const sa = analysis.scan_analyst || {}
  const actionable = insights.filter(i => {
    if (i.verdict === 'dismiss') return false
    if (i.type === 'correlated' && i.verdict !== 'escalate') return false
    return i.verdict === 'escalate' || i.verdict === 'explain' || !i.verdict
  })

  return (
    <div className="space-y-6" data-testid="scan-ai-tab">
      <div className="flex items-center gap-2 text-violet-700 dark:text-violet-300">
        <Bot className="w-5 h-5" />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">AI Analysis</h3>
      </div>

      {sa.status && sa.status !== 'not_run' && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-500/50 dark:bg-indigo-900/30">
          <h4 className="text-sm font-medium text-indigo-800 dark:text-indigo-300 mb-2 flex items-center gap-2">
            {statusIcon(sa.status)}
            Scan analyst narrative
            {sa.source && <span className="text-xs text-gray-600 dark:text-gray-500 font-normal">({sa.source})</span>}
          </h4>
          {sa.summary && (
            <p className="text-sm text-gray-900 dark:text-gray-100 font-medium mb-2">{sa.summary}</p>
          )}
          {sa.verdict && (
            <span className={`text-xs px-1.5 py-0.5 rounded border ${VERDICT_STYLES[sa.verdict] || ''}`}>
              {sa.verdict}
            </span>
          )}
          {sa.reasoning && (
            <p className="text-sm text-gray-700 dark:text-gray-300 mt-3 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
              {sa.reasoning}
            </p>
          )}
          {sa.findings?.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs text-gray-600 dark:text-gray-400">
              {sa.findings.slice(0, 8).map((f, idx) => (
                <li key={idx}>
                  <span className="text-gray-500 dark:text-gray-500">{f.verdict}:</span> {f.finding}
                </li>
              ))}
            </ul>
          )}
          {sa.skipped_reason && (
            <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">{sa.skipped_reason}</p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 dark:border-violet-500/40 dark:bg-violet-900/20">
          <h4 className="text-sm font-medium text-violet-800 dark:text-violet-300 mb-2">Insights generation</h4>
          <dl className="text-sm space-y-1 text-gray-700 dark:text-gray-300">
            <div className="flex justify-between"><dt>Count</dt><dd className="font-medium text-gray-900 dark:text-gray-100">{ig.count ?? summary.total ?? 0}</dd></div>
            {ig.previous_scan_id != null && (
              <div className="flex justify-between"><dt>Compared to scan</dt><dd className="font-medium text-gray-900 dark:text-gray-100">#{ig.previous_scan_id}</dd></div>
            )}
            {ig.at && <div className="flex justify-between"><dt>Ran at</dt><dd className="text-xs font-medium text-gray-900 dark:text-gray-100">{ig.at}</dd></div>}
            {ig.skipped_reason && (
              <div className="mt-2 text-yellow-700 dark:text-yellow-300 text-xs">{ig.skipped_reason}</div>
            )}
            {ig.error && (
              <div className="mt-2 text-red-600 dark:text-red-300 text-xs flex gap-1"><AlertTriangle className="w-3 h-3 shrink-0" />{ig.error}</div>
            )}
          </dl>
        </div>

        <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 dark:border-violet-500/40 dark:bg-violet-900/20">
          <h4 className="text-sm font-medium text-violet-800 dark:text-violet-300 mb-2 flex items-center gap-2">
            {statusIcon(va.status)}
            Verdict agent (LLM)
          </h4>
          <dl className="text-sm space-y-1 text-gray-700 dark:text-gray-300">
            <div className="flex justify-between"><dt>Status</dt><dd className="capitalize font-medium text-gray-900 dark:text-gray-100">{va.status || scanDetails?.verdict_agent_status || 'not_run'}</dd></div>
            {va.actionable_count != null && (
              <div className="flex justify-between"><dt>Actionable</dt><dd className="font-medium text-gray-900 dark:text-gray-100">{va.actionable_count}</dd></div>
            )}
            {va.patched_count != null && (
              <div className="flex justify-between"><dt>Verdicts patched</dt><dd className="font-medium text-gray-900 dark:text-gray-100">{va.patched_count}</dd></div>
            )}
            {va.duration_ms != null && (
              <div className="flex justify-between"><dt>Duration</dt><dd className="font-medium text-gray-900 dark:text-gray-100">{(va.duration_ms / 1000).toFixed(1)}s</dd></div>
            )}
            {va.skipped_reason && (
              <div className="mt-2 text-yellow-700 dark:text-yellow-300 text-xs">{va.skipped_reason}</div>
            )}
            {va.error && (
              <div className="mt-2 text-red-600 dark:text-red-300 text-xs">{va.error}</div>
            )}
          </dl>
        </div>

        <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 dark:border-violet-500/40 dark:bg-violet-900/20">
          <h4 className="text-sm font-medium text-violet-800 dark:text-violet-300 mb-2 flex items-center gap-2">
            {statusIcon(syn.status || 'not_run')}
            Synthesis agent
          </h4>
          <dl className="text-sm space-y-1 text-gray-700 dark:text-gray-300">
            <div className="flex justify-between"><dt>Status</dt><dd className="capitalize font-medium text-gray-900 dark:text-gray-100">{syn.status || 'not_run'}</dd></div>
            {syn.stories_added != null && (
              <div className="flex justify-between"><dt>Stories added</dt><dd className="font-medium text-gray-900 dark:text-gray-100">{syn.stories_added}</dd></div>
            )}
            {syn.duration_ms != null && (
              <div className="flex justify-between"><dt>Duration</dt><dd className="font-medium text-gray-900 dark:text-gray-100">{(syn.duration_ms / 1000).toFixed(1)}s</dd></div>
            )}
            {syn.skipped_reason && (
              <div className="mt-2 text-yellow-700 dark:text-yellow-300 text-xs">{syn.skipped_reason}</div>
            )}
          </dl>
        </div>
      </div>

      {(va.stderr_preview || va.stdout_preview) && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-600 dark:bg-gray-900/50">
          <h4 className="text-sm font-medium text-gray-900 dark:text-gray-200 mb-2">Agent output</h4>
          {va.stderr_preview && (
            <pre className="text-xs text-red-600 dark:text-red-300 whitespace-pre-wrap mb-2 max-h-32 overflow-y-auto">{va.stderr_preview}</pre>
          )}
          {va.stdout_preview && !showRaw && (
            <pre className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap max-h-40 overflow-y-auto">{va.stdout_preview.slice(0, 800)}{va.stdout_preview.length > 800 ? '…' : ''}</pre>
          )}
        </div>
      )}

      {va.raw_response && (
        <div>
          <button
            type="button"
            onClick={() => setShowRaw(!showRaw)}
            className="text-xs text-violet-700 hover:text-violet-900 dark:text-violet-300 dark:hover:text-violet-100 underline"
          >
            {showRaw ? 'Hide' : 'Show'} full LLM JSON response
          </button>
          {showRaw && (
            <pre className="mt-2 text-xs text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-black/40 p-3 rounded max-h-64 overflow-auto border border-gray-200 dark:border-gray-700">
              {JSON.stringify(va.raw_response, null, 2)}
            </pre>
          )}
        </div>
      )}

      <div>
        <h4 className="text-sm font-medium text-gray-900 dark:text-gray-200 mb-2">
          Insights ({summary.escalate || 0} escalate · {summary.explain || 0} explain · {summary.dismiss || 0} dismiss)
        </h4>
        {actionable.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 italic">
            {insights.length === 0
              ? 'No insights were stored for this scan. See generation panel above for why.'
              : 'All insights are dismissed or filtered.'}
          </p>
        ) : (
          <ul className="space-y-2 max-h-64 overflow-y-auto">
            {actionable.slice(0, 20).map((ins) => (
              <li key={ins.id} className="text-sm border border-gray-200 dark:border-gray-700 rounded p-2 bg-gray-50 dark:bg-gray-900/30">
                <div className="text-gray-900 dark:text-gray-100">{ins.message}</div>
                <div className="flex flex-wrap gap-2 mt-1">
                  {ins.verdict && (
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${VERDICT_STYLES[ins.verdict] || ''}`}>
                      {ins.verdict}
                    </span>
                  )}
                  <span className="text-xs text-gray-500 dark:text-gray-500">{ins.type}</span>
                </div>
                {ins.verdict_summary && (
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{ins.verdict_summary}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default ScanAiTab
