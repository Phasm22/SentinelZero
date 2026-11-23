import React from 'react'
import { Globe2, ShieldCheck } from 'lucide-react'
import LabPanel from './LabPanel'

const DnsSource = ({ label, data = {} }) => {
  const summary = data.summary || {}
  const topBlocked = Array.isArray(data.top_blocked) ? data.top_blocked.slice(0, 4) : []
  const blocked = Math.round(summary.percent_blocked || 0)

  return (
    <div className="rounded-md border border-gray-700/60 bg-gray-900/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-green-300" />
          <span className="text-sm font-semibold text-gray-100">{label}</span>
        </div>
        <span className="font-mono text-sm text-green-300">{blocked}% blocked</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="font-mono text-base text-gray-100">{summary.total_queries || 0}</div>
          <div className="card-meta">queries</div>
        </div>
        <div>
          <div className="font-mono text-base text-gray-100">{summary.blocked_queries || 0}</div>
          <div className="card-meta">blocked</div>
        </div>
      </div>
      {topBlocked.length > 0 && (
        <div className="mt-3 space-y-1">
          {topBlocked.map((entry, index) => (
            <div key={`${entry.name || entry.domain}-${index}`} className="flex items-center justify-between gap-2 text-xs">
              <span className="truncate text-gray-300">{entry.name || entry.domain}</span>
              <span className="font-mono text-gray-500">{entry.count || 0}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const DnsSummaryPanel = ({ dns = {} }) => (
  <LabPanel className="!p-4">
    <div className="mb-3 flex items-center justify-between gap-3">
      <div>
        <h2 className="card-heading text-base">DNS Protection</h2>
        <p className="card-meta">Pi-hole lab and home query summaries</p>
      </div>
      <Globe2 className="h-5 w-5 text-green-300" />
    </div>

    <div className="grid gap-3 md:grid-cols-2">
      <DnsSource label="Lab DNS" data={dns.lab} />
      <DnsSource label="Home DNS" data={dns.home} />
    </div>
  </LabPanel>
)

export default DnsSummaryPanel
