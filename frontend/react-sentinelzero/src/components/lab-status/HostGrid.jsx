import React from 'react'
import HostCard from './HostCard'

const HostGrid = ({ detailedData, filter }) => {
  if (!detailedData) return null

  const getFilteredHosts = () => {
    const allHosts = []

    if (filter === 'all' || filter === 'loopbacks') {
      allHosts.push(...(detailedData.loopbacks || []).map(host => ({
        ...host,
        layer: 'loopbacks',
        layerName: 'Loopback',
      })))
    }

    if (filter === 'all' || filter === 'services') {
      allHosts.push(...(detailedData.services || []).map(host => ({
        ...host,
        layer: 'services',
        layerName: 'Service',
      })))
    }

    if (filter === 'all' || filter === 'infrastructure') {
      allHosts.push(...(detailedData.infrastructure || []).map(host => ({
        ...host,
        layer: 'infrastructure',
        layerName: 'Infrastructure',
      })))
    }

    return allHosts
  }

  const hosts = getFilteredHosts()

  if (hosts.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="card-meta text-lg">No hosts found for the selected filter</div>
      </div>
    )
  }

  const networkScanners = hosts.filter(host => {
    const ip = host.ip || host.ping?.ip || host.dns?.ip || 'unknown'
    const name = host.name || 'Unknown'
    return ip.match(/^(1\.1\.1\.|8\.8\.8\.|208\.67\.)/)
           || name.includes('Cloudflare')
           || name.includes('Google DNS')
           || name.includes('Internet Test')
  })

  const otherHosts = hosts.filter(host => {
    const ip = host.ip || host.ping?.ip || host.dns?.ip || 'unknown'
    const name = host.name || 'Unknown'
    return !ip.match(/^(1\.1\.1\.|8\.8\.8\.|208\.67\.)/)
           && !name.includes('Cloudflare')
           && !name.includes('Google DNS')
           && !name.includes('Internet Test')
  })

  const groupedHosts = otherHosts.reduce((groups, host) => {
    const ip = host.ip || host.ping?.ip || host.dns?.ip || 'unknown'
    const name = host.name || 'Unknown'
    let segment = 'Other'

    if (ip === '127.0.0.1') {
      segment = 'Localhost'
    } else if (ip.startsWith('172.16.')) {
      if (name.toLowerCase().includes('proxmox')) {
        segment = 'Proxmox Infrastructure'
      } else if (name.toLowerCase().includes('code-server') || name.toLowerCase().includes('winvm')) {
        segment = 'Lab VMs & Services'
      } else {
        segment = 'Lab Network (172.16.x.x)'
      }
    } else if (ip.startsWith('192.168.68.')) {
      segment = 'Home Network (192.168.68.x)'
    } else if (ip.startsWith('192.168.71.')) {
      segment = 'Lab Services (192.168.71.x)'
    } else if (ip.startsWith('10.16.')) {
      segment = 'VPN (10.16.x.x)'
    } else if (name.toLowerCase().includes('dns') || host.type === 'dns') {
      segment = 'DNS Services'
    } else if (name.toLowerCase().includes('vpn')) {
      segment = 'VPN Services'
    }

    if (!groups[segment]) groups[segment] = []
    groups[segment].push(host)
    return groups
  }, {})

  const segmentOrder = [
    'Proxmox Infrastructure',
    'Lab VMs & Services',
    'Lab Network (172.16.x.x)',
    'Lab Services (192.168.71.x)',
    'Home Network (192.168.68.x)',
    'VPN (10.16.x.x)',
    'Localhost',
    'DNS Services',
    'VPN Services',
    'Other',
  ]

  const sortedGroups = segmentOrder
    .filter(segment => groupedHosts[segment] && groupedHosts[segment].length > 0)
    .map(segment => [segment, groupedHosts[segment]])

  if (networkScanners.length > 0) {
    sortedGroups.unshift(['External DNS', networkScanners])
  }

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
        <h2 className="text-xl sm:text-2xl card-title">
          Host Details
          <span className="ml-2 sm:ml-3 text-xs sm:text-sm font-normal text-gray-300">
            ({hosts.length} {hosts.length === 1 ? 'host' : 'hosts'})
          </span>
        </h2>

        {filter !== 'all' && (
          <div className="card-meta bg-gray-800/70 px-2 sm:px-3 py-1 rounded-lg border border-gray-600/50 self-start capitalize">
            Filtered: {filter}
          </div>
        )}
      </div>

      {sortedGroups.map(([segment, segmentHosts]) => (
        <div key={segment} className="space-y-2">
          <div className="flex items-center gap-3 sticky top-0 z-10 bg-transparent py-1">
            <h3 className="text-sm sm:text-base card-heading">{segment}</h3>
            <div className="flex-1 h-px bg-gradient-to-r from-gray-600/60 to-transparent" />
            <span className="card-meta font-mono">
              {segmentHosts.length}
            </span>
          </div>

          <div className="space-y-2">
            {segmentHosts.map((host, index) => (
              <HostCard
                key={`${host.ip}-${host.name}-${index}`}
                host={host}
                hideLayerBadge={filter !== 'all'}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default HostGrid
