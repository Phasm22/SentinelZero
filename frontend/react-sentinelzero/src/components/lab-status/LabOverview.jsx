import React from 'react'
import { Server, Wifi, Globe, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import AnimatedValue from '../AnimatedValue'
import LabPanel from './LabPanel'

const LabOverview = ({ healthData, detailedData }) => {
  if (!healthData || !detailedData) return null

  const getSegmentHealth = (hosts) => {
    if (!hosts?.length) return { status: 'unknown', count: 0, total: 0 }
    const up = hosts.filter((h) => h.status === 'up' || h.status === true).length
    const total = hosts.length
    const status = up === total ? 'healthy' : up > total * 0.8 ? 'warning' : 'critical'
    return { status, count: up, total }
  }

  const allHosts = [
    ...(detailedData.loopbacks || []),
    ...(detailedData.services || []),
    ...(detailedData.infrastructure || []),
  ]

  const labNetwork = allHosts.filter((h) => {
    const ip = h.ip || h.ping?.ip || h.dns?.ip || ''
    return ip.startsWith('172.16.') || ip.startsWith('192.168.71.')
  })
  const homeNetwork = allHosts.filter((h) => (h.ip || h.ping?.ip || '').startsWith('192.168.68.'))
  const externalServices = allHosts.filter((h) => {
    const ip = h.ip || h.ping?.ip || h.dns?.ip || ''
    return /^(1\.1\.1\.|8\.8\.8\.|208\.67\.)/.test(ip)
      || h.name?.includes('Cloudflare')
      || h.name?.includes('Google DNS')
  })

  const segments = [
    { name: 'Lab', icon: Server, health: getSegmentHealth(labNetwork) },
    { name: 'Home', icon: Wifi, health: getSegmentHealth(homeNetwork) },
    { name: 'External', icon: Globe, health: getSegmentHealth(externalServices) },
  ]

  const statusIcon = (status) => {
    if (status === 'healthy') return CheckCircle
    if (status === 'warning') return AlertTriangle
    if (status === 'critical') return XCircle
    return Server
  }

  return (
    <LabPanel className="!p-3 sm:!p-4">
      <div className="flex flex-wrap gap-2 sm:gap-3">
        {segments.map((segment) => {
          const Icon = segment.icon
          const StatusIcon = statusIcon(segment.health.status)
          return (
            <div
              key={segment.name}
              className="card-inner-tile flex items-center gap-2 px-3 py-2 min-w-[8rem] flex-1"
            >
              <Icon className="w-4 h-4 text-gray-300 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="card-heading text-sm">{segment.name}</div>
                <div className="card-meta font-mono">
                  <AnimatedValue value={segment.health.count} />/{segment.health.total}
                </div>
              </div>
              <StatusIcon className={`w-4 h-4 shrink-0 ${
                segment.health.status === 'healthy' ? 'text-green-400' :
                segment.health.status === 'warning' ? 'text-yellow-400' :
                segment.health.status === 'critical' ? 'text-red-400' :
                'text-gray-400'
              }`} />
            </div>
          )
        })}
      </div>
    </LabPanel>
  )
}

export default LabOverview
