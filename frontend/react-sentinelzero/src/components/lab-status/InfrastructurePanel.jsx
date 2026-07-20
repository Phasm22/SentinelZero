import React from 'react'
import { Database, HardDrive, Server } from 'lucide-react'
import LabPanel from './LabPanel'
import HealthIndicator from './HealthIndicator'

const InfrastructurePanel = ({ infrastructure = {}, reachability = {} }) => {
  const proxmox = infrastructure.proxmox || {}
  const nodes = Array.isArray(proxmox.nodes) ? proxmox.nodes : []
  const infraItems = Array.isArray(reachability.infrastructure?.items)
    ? reachability.infrastructure.items.slice(0, 8)
    : []

  return (
    <LabPanel className="!p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="card-heading text-base">Infrastructure</h2>
          <p className="card-meta">Proxmox nodes, guests, and core reachability</p>
        </div>
        <Server className="h-5 w-5 text-cyan-300" />
      </div>

      <div className="grid grid-cols-3 gap-2">
        {[
          ['Nodes', proxmox.node_count || nodes.length || 0, Server],
          ['Guests', proxmox.guest_count || 0, Database],
          ['Running', proxmox.running_guests || 0, HardDrive],
        ].map(([label, value, Icon]) => (
          <div key={label} className="card-inner-tile px-3 py-2">
            <div className="flex items-center gap-2">
              <Icon className="h-4 w-4 text-gray-400" />
              <span className="font-mono text-lg font-semibold text-gray-100">{value}</span>
            </div>
            <div className="card-meta">{label}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-2">
        {nodes.map((node) => (
          <div key={node.node || node.agent_id} className="flex items-center gap-3 rounded-md border border-gray-700/60 bg-gray-900/40 px-3 py-2">
            <HealthIndicator status={node.status === 'online' || node.node_status === 'online' ? 'healthy' : 'warning'} size="xs" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-gray-100">{node.node || node.agent_id}</div>
              <div className="truncate text-xs text-gray-500">{node.guest_count || 0} guests · {node.running_guests || 0} running</div>
            </div>
          </div>
        ))}
        {infraItems.map((item, index) => (
          <div key={`${item.name}-${index}`} className="flex items-center gap-3 rounded-md border border-gray-700/60 bg-gray-900/40 px-3 py-2">
            <HealthIndicator status={item.status === 'up' ? 'healthy' : 'critical'} size="xs" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-gray-100">{item.name || item.ip}</div>
              <div className="truncate text-xs font-mono text-gray-500">{item.ip || item.domain || item.type}</div>
            </div>
          </div>
        ))}
      </div>
    </LabPanel>
  )
}

export default InfrastructurePanel
