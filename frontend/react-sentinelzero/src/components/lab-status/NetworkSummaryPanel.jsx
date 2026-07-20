import React from 'react'
import { Network, ShieldAlert, Wifi } from 'lucide-react'
import LabPanel from './LabPanel'
import HealthIndicator from './HealthIndicator'

const NetworkSummaryPanel = ({ network = {}, flows = {} }) => {
  const opnsense = network.opnsense || {}
  const inventory = network.inventory || {}
  const gatewaysDown = opnsense.gateway_down_count || 0
  const idsCount = opnsense.ids?.alert_count || 0
  const flaggedHosts = Array.isArray(flows.flagged_hosts) ? flows.flagged_hosts.slice(0, 5) : []

  return (
    <LabPanel className="!p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="card-heading text-base">Network Core</h2>
          <p className="card-meta">OPNsense inventory, gateways, IDS, and ntopng flows</p>
        </div>
        <HealthIndicator status={gatewaysDown || idsCount ? 'warning' : opnsense.status === 'available' ? 'healthy' : 'unknown'} variant="pill" size="sm" showText />
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {[
          ['DHCP leases', inventory.dhcp_lease_count || 0, Wifi],
          ['ARP entries', inventory.arp_entry_count || 0, Network],
          ['Active flows', flows.active_host_count || 0, Network],
          ['IDS alerts', idsCount, ShieldAlert],
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

      {flaggedHosts.length > 0 && (
        <div className="mt-3 space-y-2">
          <div className="card-meta uppercase tracking-wide">Flagged ntopng Hosts</div>
          {flaggedHosts.map((host, index) => (
            <div key={`${host.ip || host.name}-${index}`} className="flex items-center justify-between gap-3 rounded-md bg-gray-900/40 px-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-gray-100">{host.name || host.ip || 'unknown host'}</div>
                <div className="truncate text-xs font-mono text-gray-500">{host.ip || 'no ip'}</div>
              </div>
              <div className="text-right">
                <div className="font-mono text-sm text-yellow-300">{Math.round(host.score || 0)}</div>
                <div className="card-meta">score</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </LabPanel>
  )
}

export default NetworkSummaryPanel
