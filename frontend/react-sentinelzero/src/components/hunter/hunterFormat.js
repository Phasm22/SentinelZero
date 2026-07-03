// Shared formatting + derivation helpers for the Hunter Runs view.
// Pure functions only (no JSX) so they can be unit-tested and reused.

// Action-priority tiers, mirroring the green/amber/blue/gray language used by
// HealthIndicator + the lab-status cards.
export const ACTION_TIERS = {
  now: {
    label: 'Act now',
    text: 'text-red-300',
    bg: 'bg-red-500/20',
    border: 'border-red-500/40',
    glow: 'shadow-red-500/20',
    dot: 'bg-red-400',
    accent: 'border-l-red-500/70',
  },
  next_scan: {
    label: 'Next scan',
    text: 'text-amber-300',
    bg: 'bg-amber-500/20',
    border: 'border-amber-500/40',
    glow: 'shadow-amber-500/20',
    dot: 'bg-amber-400',
    accent: 'border-l-amber-500/70',
  },
  observe: {
    label: 'Observe',
    text: 'text-blue-300',
    bg: 'bg-blue-500/20',
    border: 'border-blue-500/40',
    glow: 'shadow-blue-500/20',
    dot: 'bg-blue-400',
    accent: 'border-l-blue-500/70',
  },
  none_until_online: {
    label: 'When online',
    text: 'text-gray-300',
    bg: 'bg-gray-500/20',
    border: 'border-gray-500/40',
    glow: 'shadow-gray-500/20',
    dot: 'bg-gray-400',
    accent: 'border-l-gray-500/70',
  },
}

export const SEVERITY_TIERS = {
  high: {
    label: 'High',
    text: 'text-red-300',
    bg: 'bg-red-500/20',
    border: 'border-red-500/40',
    dot: 'bg-red-400',
    bar: 'from-red-500 to-red-400',
    rank: 0,
  },
  medium: {
    label: 'Medium',
    text: 'text-amber-300',
    bg: 'bg-amber-500/20',
    border: 'border-amber-500/40',
    dot: 'bg-amber-400',
    bar: 'from-amber-500 to-amber-400',
    rank: 1,
  },
  low: {
    label: 'Low',
    text: 'text-blue-300',
    bg: 'bg-blue-500/20',
    border: 'border-blue-500/40',
    dot: 'bg-blue-400',
    bar: 'from-blue-500 to-blue-400',
    rank: 2,
  },
  info: {
    label: 'Info',
    text: 'text-gray-300',
    bg: 'bg-gray-500/20',
    border: 'border-gray-500/40',
    dot: 'bg-gray-400',
    bar: 'from-gray-500 to-gray-400',
    rank: 3,
  },
}

export const actionTier = (priority) => ACTION_TIERS[priority] || ACTION_TIERS.observe
export const severityTier = (severity) => SEVERITY_TIERS[severity] || SEVERITY_TIERS.info

// Severity for an event type, mirroring backend _event_severity so the UI can
// color the "What Changed" chips even though the histogram is keyed by type.
const TYPE_SEVERITY = {
  expected_udp_violation: 'high',
  new_device: 'high',
  new_udp_port: 'medium',
  new_host: 'medium',
  lost_udp_port: 'low',
  iot_observation: 'low',
}
export const typeSeverity = (type) => TYPE_SEVERITY[type] || 'info'

const FINGERPRINT_TYPES = new Set([
  'new_device',
  'new_udp_port',
  'lost_udp_port',
  'expected_udp_violation',
])

// Relative timestamp, ported from HealthOverview's getTimeAgo.
export function timeAgo(ts) {
  if (!ts) return 'unknown'
  try {
    const then = new Date(ts)
    if (Number.isNaN(then.getTime())) return String(ts)
    const diffMs = Date.now() - then.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  } catch {
    return 'unknown'
  }
}

export function fmtTime(ts) {
  if (!ts) return 'Unknown'
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return String(ts)
  return date.toLocaleString()
}

const SCAN_STATUS = {
  triggered: { label: 'Scan triggered', status: 'healthy' },
  skipped: { label: 'Scan skipped', status: 'unknown' },
  failed: { label: 'Scan failed', status: 'critical' },
  none: { label: 'No scan', status: 'unknown' },
}
export const scanStatusMeta = (status) => SCAN_STATUS[status] || SCAN_STATUS.none

const hostHasSignal = (host) =>
  (host?.noveltyScore || 0) > 0 ||
  (host?.driftScore || 0) > 0 ||
  (host?.event_count || 0) > 0

// The aggregation layer: turn a normalized run into operator-facing insight so
// the page can lead with meaning instead of dumping uniform rows.
export function deriveRunInsight(run) {
  const meta = run?.huntRun || {}
  const hosts = run?.huntHost || []
  const events = run?.huntEvent || []
  const eventTotal = run?.whatChanged?.eventTotal ?? events.length
  const histogram = run?.whatChanged?.eventHistogram || {}

  const actionCounts = hosts.reduce((acc, host) => {
    const key = host.actionPriority || 'observe'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})

  const severityCounts = events.reduce((acc, ev) => {
    const key = ev.severity || 'info'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})

  const signalHosts = hosts.filter(hostHasSignal)
  const quietHosts = hosts.filter((host) => !hostHasSignal(host))

  const isInventory = eventTotal === 0
  const nowCount = actionCounts.now || 0
  const nextCount = actionCounts.next_scan || 0

  let headline
  if (isInventory) {
    headline = `Inventory sweep — ${hosts.length} host${hosts.length === 1 ? '' : 's'} mapped, no anomalies`
    if (nextCount > 0) {
      headline = `Inventory sweep — ${nextCount} host${nextCount === 1 ? '' : 's'} queued, no anomalies`
    }
  } else if (nowCount > 0) {
    headline = `${nowCount} host${nowCount === 1 ? '' : 's'} flagged to act on now`
  } else if (nextCount > 0) {
    headline = `${nextCount} host${nextCount === 1 ? '' : 's'} queued for the next scan`
  } else {
    headline = `${eventTotal} change${eventTotal === 1 ? '' : 's'} observed`
  }

  // Fingerprint-class events (the "continuity" story).
  const fingerprintEvents = Object.entries(histogram)
    .filter(([type]) => FINGERPRINT_TYPES.has(type))
    .sort((a, b) => severityTier(typeSeverity(a[0])).rank - severityTier(typeSeverity(b[0])).rank)

  return {
    verdict: isInventory ? 'Inventory sweep' : 'Assessment',
    isInventory,
    headline,
    actionCounts,
    severityCounts,
    signalHosts,
    quietHosts,
    baselineUpdates: meta?.baselineUpdated?.count ?? 0,
    fingerprintEvents,
  }
}

// ── Service / port interpretation ────────────────────────────────────────────
// open_ports entries are objects {port, protocol, service, state}; udp_ports are
// bare numbers. Normalize both into one shape the UI can render + reason about.
const SERVICE_LABELS = {
  domain: 'DNS',
  dhcps: 'DHCP server',
  dhcpc: 'DHCP client',
  http: 'web UI',
  'http-alt': 'web UI',
  https: 'secure web UI',
  rtsp: 'RTSP video',
  upnp: 'UPnP/SSDP',
  zeroconf: 'mDNS/Bonjour',
  ntp: 'NTP time',
  snmp: 'SNMP mgmt',
  ssh: 'SSH',
  telnet: 'Telnet',
}

const PORT_SERVICE = {
  53: 'domain', 67: 'dhcps', 68: 'dhcpc', 80: 'http', 123: 'ntp', 161: 'snmp',
  443: 'https', 554: 'rtsp', 1900: 'upnp', 5353: 'zeroconf', 8080: 'http-alt',
}

export function normalizePort(entry, fallbackProto = 'udp') {
  if (entry && typeof entry === 'object') {
    const port = entry.port
    const protocol = entry.protocol || fallbackProto
    const service = entry.service || PORT_SERVICE[port] || null
    return { port, protocol, service }
  }
  // bare number (udp_ports)
  return { port: entry, protocol: fallbackProto, service: PORT_SERVICE[entry] || null }
}

export const friendlyService = (service) => SERVICE_LABELS[service] || service

// Union of every observed port across all of a host's events, deduped.
export function hostPorts(host) {
  const seen = new Map()
  for (const ev of host?.events || []) {
    for (const p of ev.open_ports || []) {
      const n = normalizePort(p, 'tcp')
      seen.set(`${n.protocol}/${n.port}`, n)
    }
    for (const p of ev.udp_ports || []) {
      const n = normalizePort(p, 'udp')
      seen.set(`${n.protocol}/${n.port}`, n)
    }
  }
  return Array.from(seen.values()).sort((a, b) => a.port - b.port)
}

// Plain-English device inference from the service/port fingerprint. This is the
// "what is this thing" layer — deterministic, derived from the discovery
// protocols a host speaks (DNS, mDNS, UPnP, RTSP, DHCP, web).
export function classifyHost(host) {
  const ports = hostPorts(host)
  const services = new Set(ports.map((p) => p.service).filter(Boolean))
  const has = (s) => services.has(s)

  const present = []
  if (has('zeroconf')) present.push('advertises over mDNS/Bonjour (5353)')
  if (has('upnp')) present.push('announces via UPnP/SSDP (1900)')
  if (has('rtsp')) present.push('serves an RTSP video stream (554)')
  if (has('dhcps')) present.push('runs a DHCP server (67)')
  if (has('domain')) present.push('answers DNS (53)')
  if (has('https') || has('http') || has('http-alt')) present.push('exposes a web interface')
  if (has('snmp')) present.push('is SNMP-managed (161)')

  // Order matters: strongest identity signals first. DNS-serving and RTSP are
  // unambiguous; mDNS+UPnP discovery beats a lone (often nmap-ambiguous) DHCP
  // port for classifying consumer gear.
  let label = 'Unclassified host'
  if (has('domain')) {
    label = 'Router / gateway / DNS resolver'
  } else if (has('rtsp')) {
    label = 'IP camera / video device'
  } else if (has('zeroconf') && has('upnp')) {
    label = 'Smart-home / IoT device'
  } else if (has('dhcps')) {
    label = 'DHCP server / gateway'
  } else if (has('zeroconf') || has('upnp')) {
    label = 'Networked media / smart device'
  } else if (has('https') || has('http') || has('http-alt')) {
    label = 'Device with a web interface'
  } else if (has('dhcpc')) {
    label = 'Generic network client'
  }

  let summary
  if (present.length === 0) {
    summary = ports.length
      ? 'No identifying discovery or service protocols observed yet.'
      : 'No open ports captured in this run — queued for a deeper scan.'
  } else {
    const joined =
      present.length === 1
        ? present[0]
        : `${present.slice(0, -1).join(', ')} and ${present[present.length - 1]}`
    summary = `This host ${joined} — ${label.toLowerCase()}.`
  }

  return { label, summary, services: Array.from(services), portCount: ports.length }
}

// Histogram entries sorted high → low severity for the What Changed chips.
export function sortedHistogram(histogram = {}) {
  return Object.entries(histogram).sort((a, b) => {
    const sev = severityTier(typeSeverity(a[0])).rank - severityTier(typeSeverity(b[0])).rank
    if (sev !== 0) return sev
    return b[1] - a[1]
  })
}
