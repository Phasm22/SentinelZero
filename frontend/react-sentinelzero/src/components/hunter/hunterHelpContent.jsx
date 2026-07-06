import React from 'react'

export const InsightsCardHelp = () => (
  <>
    <p className="card-body">
      Insights are post-scan findings triaged by the blue agent into escalate, explain, or dismiss.
      They appear here after a scan completes and the verdict pipeline runs.
    </p>
    <p className="card-body">
      <strong className="text-gray-200">Pivot missions</strong> are started manually — they never
      auto-launch from escalate. Expand an insight row to look for{' '}
      <strong className="text-gray-200">Start pivot mission</strong>.
    </p>
    <ul className="list-disc list-inside space-y-1 card-meta">
      <li>Verdict must be <span className="text-red-300">escalate</span></li>
      <li>Network must be <span className="text-blue-300">Lab</span> (Home insights are excluded)</li>
      <li>Host must be a single IP address</li>
      <li>Type: new host, new port, service change, critical/high vuln, gap (sensor, registry,
      inventory), or a correlated finding cluster</li>
    </ul>
    <p className="card-muted">
      Baseline, resolved-vuln, and scan-performance insights are never pivot-eligible.
    </p>
  </>
)

export const PivotMissionButtonHelp = () => (
  <>
    <p className="card-body">
      Starts a bounded red-team pivot chain from this insight&apos;s host — typically nmap recon,
      triage, then deeper enumeration if warranted.
    </p>
    <p className="card-body">
      The mission runs in the background on this server. Progress appears under{' '}
      <strong className="text-gray-200">Hunter Runs → Pivot Missions</strong>. When complete, the
      report shows in the run timeline with a pivot chain view.
    </p>
    <ul className="list-disc list-inside space-y-1 card-meta">
      <li>Passive steps run automatically</li>
      <li>Active steps (e.g. SMB enum) may stall until approved on the Hunter CLI</li>
      <li>Findings are embedded into incident memory with source &quot;mission&quot;</li>
    </ul>
  </>
)

export const HunterRunsPageHelp = () => (
  <>
    <p className="card-body">This page shows two kinds of Hunter output:</p>
    <ul className="list-disc list-inside space-y-2 card-meta">
      <li>
        <strong className="text-gray-200">Inventory / assess runs</strong> — scheduled missions
        (lab inventory, home assess) that diff sensors vs scans and recommend follow-up scans.
      </li>
      <li>
        <strong className="text-gray-200">Pivot runs</strong> — manual deep-dives seeded from an
        escalated Lab insight on the dashboard. Look for{' '}
        <span className="font-mono text-purple-300">pivot-*</span> mission IDs and the pivot chain panel.
      </li>
    </ul>
    <p className="card-muted">
      Inventory runs are not started from this page. Pivot runs are started from Dashboard → Recent
      Insights → expand an eligible insight.
    </p>
  </>
)

export const PivotMissionsPanelHelp = () => (
  <>
    <p className="card-body">Live status for manually spawned pivot missions.</p>
    <ul className="list-disc list-inside space-y-1 card-meta">
      <li><span className="text-blue-300">running</span> — orchestrator is active</li>
      <li><span className="text-yellow-300">stalled</span> — waiting for approval or no heartbeat</li>
      <li><span className="text-green-300">done</span> — report written to hunt-*.json</li>
      <li><span className="text-red-300">failed</span> — check mission log on the server</li>
    </ul>
    <p className="card-muted">
      When done, select the matching run in the timeline to see the pivot chain and findings.
    </p>
  </>
)
