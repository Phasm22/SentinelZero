import React from 'react'
import { Activity, Clock, Radar, ServerCog, Users, Network } from 'lucide-react'
import { timeAgo, fmtTime, scanStatusMeta, actionTier } from './hunterFormat'

const STATUS_DOT = {
  healthy: 'bg-green-400 shadow-green-400/50',
  critical: 'bg-red-400 shadow-red-400/50',
  unknown: 'bg-gray-400 shadow-gray-400/50',
}

const Kpi = ({ icon: Icon, label, value, valueClass = 'text-gray-100' }) => (
  <div className="bg-gray-700/40 border border-gray-600/30 rounded-lg p-4 flex flex-col gap-1 transition-all duration-200 hover:bg-gray-700/60">
    <div className="flex items-center gap-2 text-gray-300">
      <Icon className="w-4 h-4 flex-shrink-0" />
      <span className="text-[11px] uppercase tracking-wide whitespace-nowrap">{label}</span>
    </div>
    <div className={`text-2xl font-bold font-mono ${valueClass}`}>{value}</div>
  </div>
)

const HunterRunHeader = ({ run, insight }) => {
  const meta = run.huntRun || {}
  const scan = scanStatusMeta(meta.scanTriggerStatus)
  const known = meta?.deviceContextSummary?.known
  const unknown = meta?.deviceContextSummary?.unknown
  const nowTier = actionTier('now')

  return (
    <div className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-md shadow-xl p-4 sm:p-6 transition-all duration-200 hover:shadow-2xl">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-gray-400">
            <Radar className="w-4 h-4 text-blue-400" />
            {insight.verdict}
          </div>
          <h2 className="mt-1 text-xl sm:text-2xl font-bold text-gray-100 leading-tight">
            {insight.headline}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-300 font-mono">
            <span className="text-gray-200">{meta.missionId || 'run'}</span>
            <span className="text-gray-500">·</span>
            <span>{meta.targetNetwork || 'n/a'}</span>
            <span className="text-gray-500">·</span>
            <span className="inline-flex items-center gap-1 text-gray-400">
              <Clock className="w-3.5 h-3.5" />
              {timeAgo(meta.completedAt)}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-sm font-medium ${
              scan.status === 'healthy'
                ? 'bg-green-500/20 border-green-500/30 text-green-300'
                : scan.status === 'critical'
                ? 'bg-red-500/20 border-red-500/30 text-red-300'
                : 'bg-gray-500/20 border-gray-500/30 text-gray-300'
            }`}
          >
            <span className={`w-2 h-2 rounded-full shadow-sm ${STATUS_DOT[scan.status]}`} />
            {scan.label}
          </span>
          <span className="inline-flex items-center px-3 py-1 rounded-full border border-gray-600/50 bg-gray-800/70 text-sm text-gray-200">
            {meta.hostsRecommendedTotal || 0} recommended
          </span>
          {meta.hostsRecommendedCapped && (
            <span className={`inline-flex items-center px-3 py-1 rounded-full border text-sm ${nowTier.bg} ${nowTier.border} ${nowTier.text}`}>
              capped
            </span>
          )}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Kpi icon={Activity} label="Events" value={run.whatChanged?.eventTotal || 0} valueClass={insight.isInventory ? 'text-gray-400' : 'text-blue-300'} />
        <Kpi icon={Network} label="Hosts" value={run.whatChanged?.hostTotal || 0} />
        <Kpi icon={ServerCog} label="Known" value={Number.isFinite(known) ? known : '—'} valueClass="text-green-300" />
        <Kpi icon={Users} label="Unknown" value={Number.isFinite(unknown) ? unknown : '—'} valueClass={unknown ? 'text-amber-300' : 'text-gray-100'} />
      </div>
    </div>
  )
}

export default HunterRunHeader
