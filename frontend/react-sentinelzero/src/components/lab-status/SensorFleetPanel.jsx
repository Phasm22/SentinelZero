import React from 'react'
import { Activity, Cpu, Radio, Server } from 'lucide-react'
import LabPanel from './LabPanel'
import HealthIndicator from './HealthIndicator'

const statusTone = {
  active: 'text-green-300',
  stale: 'text-yellow-300',
  offline: 'text-red-300',
  unknown: 'text-gray-300',
}

const SensorFleetPanel = ({ fleet = {} }) => {
  const agents = Array.isArray(fleet.agents) ? fleet.agents.slice(0, 10) : []
  const coverage = fleet.collector_coverage || {}

  return (
    <LabPanel className="!p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="card-heading text-base">Sensor Fleet</h2>
          <p className="card-meta">Endpoint, Proxmox, and network collector freshness</p>
        </div>
        <Radio className="h-5 w-5 text-blue-300" />
      </div>

      <div className="grid grid-cols-3 gap-2">
        {[
          ['Active', fleet.active || 0, 'text-green-300'],
          ['Stale', fleet.stale || 0, 'text-yellow-300'],
          ['Offline', fleet.offline || 0, 'text-red-300'],
        ].map(([label, value, color]) => (
          <div key={label} className="card-inner-tile px-3 py-2">
            <div className={`font-mono text-lg font-semibold ${color}`}>{value}</div>
            <div className="card-meta">{label}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {Object.entries(coverage).slice(0, 8).map(([name, count]) => (
          <span key={name} className="rounded-md border border-gray-600/50 bg-gray-800/50 px-2 py-1 text-xs text-gray-300">
            <span className="font-mono text-gray-100">{count}</span> {name}
          </span>
        ))}
      </div>

      <div className="mt-4 space-y-2">
        {agents.map((agent) => {
          const status = agent.status || 'unknown'
          return (
            <div key={agent.agent_id} className="flex items-center gap-3 rounded-md border border-gray-700/60 bg-gray-900/40 px-3 py-2">
              <HealthIndicator status={status === 'active' ? 'healthy' : status === 'stale' ? 'warning' : status === 'offline' ? 'critical' : 'unknown'} size="xs" />
              <Server className="h-4 w-4 shrink-0 text-gray-400" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-gray-100">{agent.hostname || agent.agent_id}</div>
                <div className="truncate text-xs text-gray-500">{agent.role || 'sensor'} · {agent.host_ip || 'no ip'}</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {agent.latest_collectors?.system && <Cpu className="h-3.5 w-3.5 text-gray-400" />}
                <span className={`text-xs font-mono uppercase ${statusTone[status] || statusTone.unknown}`}>
                  {status}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </LabPanel>
  )
}

export default SensorFleetPanel
