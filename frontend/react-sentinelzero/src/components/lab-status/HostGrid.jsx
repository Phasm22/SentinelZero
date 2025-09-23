import React from 'react'
import HostCard from './HostCard'

const HostGrid = ({ detailedData, filter }) => {
  if (!detailedData) return null

  // Combine and filter data based on selected filter
  const getFilteredHosts = () => {
    const allHosts = []
    
    if (filter === 'all' || filter === 'loopbacks') {
      allHosts.push(...(detailedData.loopbacks || []).map(host => ({ 
        ...host, 
        layer: 'loopbacks',
        layerName: 'Loopback'
      })))
    }
    
    if (filter === 'all' || filter === 'services') {
      allHosts.push(...(detailedData.services || []).map(host => ({ 
        ...host, 
        layer: 'services',
        layerName: 'Service'
      })))
    }
    
    if (filter === 'all' || filter === 'infrastructure') {
      allHosts.push(...(detailedData.infrastructure || []).map(host => ({ 
        ...host, 
        layer: 'infrastructure',
        layerName: 'Infrastructure'
      })))
    }
    
    return allHosts
  }

  const hosts = getFilteredHosts()

  if (hosts.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-gray-400 dark:text-gray-400 text-lg">No hosts found for the selected filter</div>
      </div>
    )
  }

  // Group hosts by proper network categories and layer purpose
  const groupedHosts = hosts.reduce((groups, host) => {
    const ip = host.ip || host.ping?.ip || host.dns?.ip || 'unknown'
    const name = host.name || 'Unknown'
    let segment = 'Other'
    
    // Determine proper network segment based on IP and function
    if (ip === '127.0.0.1') {
      segment = 'Localhost'
    } else if (ip.startsWith('172.16.')) {
      // Lab network (172.16.0.0/22) - categorize by function
      if (name.toLowerCase().includes('proxmox')) {
        segment = 'Proxmox Infrastructure'
      } else if (name.toLowerCase().includes('code-server') || name.toLowerCase().includes('winvm')) {
        segment = 'Lab VMs & Services'
      } else {
        segment = 'Lab Network (172.16.x.x)'
      }
    } else if (ip.startsWith('192.168.68.')) {
      // Home network (192.168.68.0/22)  
      segment = 'Home Network (192.168.68.x)'
    } else if (ip.startsWith('192.168.71.')) {
      // Additional lab services (192.168.71.x)
      segment = 'Lab Services (192.168.71.x)'
    } else if (ip.startsWith('10.16.')) {
      // VPN network
      segment = 'VPN (10.16.x.x)'
    } else if (ip.match(/^(1\.1\.1\.|8\.8\.8\.|208\.67\.)/)) {
      segment = 'External DNS'
    } else {
      // Check by host function/name for special cases
      if (name.toLowerCase().includes('dns') || host.type === 'dns') {
        segment = 'DNS Services'
      } else if (name.toLowerCase().includes('vpn')) {
        segment = 'VPN Services'
      }
    }
    
    if (!groups[segment]) groups[segment] = []
    groups[segment].push(host)
    return groups
  }, {})

  // Define the display order for network segments
  const segmentOrder = [
    'Proxmox Infrastructure',     // Proxmox cluster nodes
    'Lab VMs & Services',         // Lab VMs and services
    'Lab Network (172.16.x.x)',  // Other lab network devices
    'Lab Services (192.168.71.x)', // Additional lab services
    'Home Network (192.168.68.x)', // Home network
    'VPN (10.16.x.x)',            // VPN endpoints
    'Localhost',                  // Local system
    'DNS Services',               // DNS-specific services
    'VPN Services',               // VPN-specific services  
    'External DNS',               // External DNS servers
    'Other'                       // Everything else
  ]

  // Sort the grouped hosts by the defined order
  const sortedGroups = segmentOrder
    .filter(segment => groupedHosts[segment] && groupedHosts[segment].length > 0)
    .map(segment => [segment, groupedHosts[segment]])

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-300 dark:text-gray-300">
          Host Details
          <span className="ml-2 sm:ml-3 text-xs sm:text-sm font-normal text-gray-400 dark:text-gray-400">
            ({hosts.length} {hosts.length === 1 ? 'host' : 'hosts'})
          </span>
        </h2>
        
        {filter !== 'all' && (
          <div className="text-xs sm:text-sm text-gray-400 dark:text-gray-400 bg-white/10 dark:bg-white/10 px-2 sm:px-3 py-1 rounded-lg border border-white/20 dark:border-white/20 self-start capitalize">
            Filtered: {filter}
          </div>
        )}
      </div>

      {sortedGroups.map(([segment, segmentHosts]) => (
        <div key={segment} className="space-y-3 sm:space-y-4">
          <div className="flex items-center gap-3">
            <h3 className="text-base sm:text-lg font-semibold text-gray-300 dark:text-gray-300">{segment}</h3>
            <div className="flex-1 h-px bg-gradient-to-r from-gray-600 dark:from-gray-600 to-transparent"></div>
            <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-500">
              {segmentHosts.length} {segmentHosts.length === 1 ? 'host' : 'hosts'}
            </span>
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
            {segmentHosts.map((host, index) => (
              <HostCard 
                key={`${host.ip}-${host.name}-${index}`} 
                host={host} 
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default HostGrid
