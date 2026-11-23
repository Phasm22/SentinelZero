import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  Clock,
  Crosshair,
  Plus,
  Radar,
  RefreshCw,
  Trash2,
  Wrench,
} from 'lucide-react'
import { apiService } from '../utils/api'
import { useToast } from '../contexts/ToastContext'
import Toggle from '../components/Toggle'
import Button from '../components/Button'

const SCAN_TYPES = ['Discovery Scan', 'Full TCP', 'IoT Scan', 'Vuln Scripts']
const SCAN_NETWORKS = [
  { cidr: '172.16.0.0/22', label: 'Lab - 172.16.0.0/22' },
  { cidr: '192.168.68.0/22', label: 'Home - 192.168.68.0/22' },
]

const emptyJob = () => ({
  id: `nmap_${Date.now().toString(36)}`,
  enabled: true,
  scanType: 'Discovery Scan',
  targetNetwork: '172.16.0.0/22',
  minute: '0',
  hour: '2',
  day: '*',
  month: '*',
  dayOfWeek: '*',
})

const cronToTime = (job) => {
  if (job.hour === '*' || job.minute === '*') return '02:00'
  const h = String(job.hour ?? '0').padStart(2, '0')
  const m = String(job.minute ?? '0').padStart(2, '0')
  return `${h}:${m}`
}

const applyTimeToJob = (job, timeStr) => {
  const [h, m] = (timeStr || '02:00').split(':')
  return {
    ...job,
    hour: String(parseInt(h, 10) || 0),
    minute: String(parseInt(m, 10) || 0),
  }
}

const frequencyFromJob = (job) => {
  if (job.hour === '*') return 'hourly'
  if (job.dayOfWeek && job.dayOfWeek !== '*') return 'weekly'
  if (job.day && job.day !== '*') return 'monthly'
  return 'daily'
}

const applyFrequency = (job, frequency) => {
  const time = cronToTime(job)
  const [h, m] = time.split(':')
  if (frequency === 'hourly') {
    return { ...job, minute: m, hour: '*', day: '*', month: '*', dayOfWeek: '*' }
  }
  if (frequency === 'weekly') {
    return { ...job, minute: m, hour: h, day: '*', month: '*', dayOfWeek: '0' }
  }
  if (frequency === 'monthly') {
    return { ...job, minute: m, hour: h, day: '1', month: '*', dayOfWeek: '*' }
  }
  return { ...job, minute: m, hour: h, day: '*', month: '*', dayOfWeek: '*' }
}

const formatNextRun = (iso) => {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

const Section = ({ icon: Icon, title, action, children }) => (
  <section className="bg-gradient-to-br from-gray-800/80 to-gray-900/60 backdrop-blur-lg border border-white/10 dark:border-gray-700 rounded-lg shadow-xl">
    <div className="px-6 py-4 border-b border-white/10 dark:border-gray-700 flex items-center justify-between gap-3">
      <div className="flex items-center space-x-2">
        <Icon className="h-5 w-5 text-green-500" />
        <h2 className="text-xl font-title font-bold text-gray-100">{title}</h2>
      </div>
      {action}
    </div>
    <div className="p-6 space-y-4">{children}</div>
  </section>
)

const stripRuntimeFields = (jobs) => (
  jobs.map(({ nextRunTime, apschedulerJobId, ...job }) => job)
)

const Schedules = () => {
  const { showToast } = useToast()
  const [jobs, setJobs] = useState([])
  const [timers, setTimers] = useState([])
  const [maintenance, setMaintenance] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [scanRes, timerRes, maintRes] = await Promise.all([
        apiService.getScheduledScans(),
        apiService.getHunterTimers().catch(() => ({ timers: [] })),
        apiService.getMaintenanceJobs().catch(() => ({ jobs: [] })),
      ])
      setJobs(Array.isArray(scanRes?.jobs) ? scanRes.jobs : [])
      setTimers(Array.isArray(timerRes?.timers) ? timerRes.timers : [])
      setMaintenance(Array.isArray(maintRes?.jobs) ? maintRes.jobs : [])
    } catch (err) {
      console.error(err)
      setError('Failed to load schedules')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const handleSaveJobs = async (nextJobs) => {
    setSaving(true)
    try {
      const payload = stripRuntimeFields(nextJobs)
      const res = await apiService.saveScheduledScans(payload)
      setJobs(res.jobs || payload)
      showToast('Nmap schedules saved', 'success')
    } catch (err) {
      console.error(err)
      showToast(err?.response?.data?.message || 'Failed to save schedules', 'danger')
    } finally {
      setSaving(false)
    }
  }

  const updateJob = (id, patch) => {
    setJobs((prev) => prev.map((job) => (job.id === id ? { ...job, ...patch } : job)))
  }

  const addJob = () => {
    setJobs((prev) => [...prev, emptyJob()])
  }

  const removeJob = (id) => {
    const next = jobs.filter((job) => job.id !== id)
    setJobs(next)
    handleSaveJobs(next)
  }

  const patchTimer = async (name, payload) => {
    try {
      const res = await apiService.patchHunterTimer(name, payload)
      if (res.status !== 'success') {
        showToast(res.message || 'Timer update failed', 'danger')
        return
      }
      setTimers((prev) => prev.map((timer) => (timer.name === name ? res.timer : timer)))
      showToast('Hunter timer updated', 'success')
    } catch (err) {
      showToast(
        err?.response?.data?.message || err?.response?.data?.hint || 'Timer update failed',
        'danger'
      )
    }
  }

  if (loading) {
    return <div className="p-8 text-center text-gray-400">Loading schedules...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-title font-bold text-gray-100 flex items-center gap-3">
            <Clock className="h-8 w-8 text-green-400" />
            Schedules
          </h1>
          <p className="text-gray-400 mt-1">
            Background and scheduled work. Manual scan runs appear only in{' '}
            <Link to="/scan-history" className="text-blue-400 hover:underline">
              Scan History
            </Link>
            .
          </p>
        </div>
        <Button variant="outline" size="sm" icon={<RefreshCw className="w-4 h-4" />} onClick={loadAll}>
          Refresh
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-300 bg-red-900/20 border border-red-700/40 rounded-md px-4 py-3">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}

      <Section
        icon={Clock}
        title="Nmap Scheduled Scans"
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" icon={<Plus className="w-4 h-4" />} onClick={addJob}>
              Add job
            </Button>
            <Button size="sm" disabled={saving} onClick={() => handleSaveJobs(jobs)}>
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        }
      >
        {jobs.length === 0 ? (
          <p className="text-gray-400 text-sm">
            No nmap jobs configured. Add one to run Discovery, Full TCP, IoT, or Vuln on a schedule.
          </p>
        ) : (
          <div className="space-y-4">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-end bg-gray-900/40 border border-gray-700/60 rounded-md p-4"
              >
                <div className="lg:col-span-1 flex items-center gap-2 pb-2">
                  <Toggle
                    checked={!!job.enabled}
                    onChange={(checked) => updateJob(job.id, { enabled: checked })}
                  />
                </div>
                <div className="lg:col-span-2">
                  <label className="block text-xs text-gray-400 mb-1">Type</label>
                  <select
                    value={job.scanType}
                    onChange={(e) => updateJob(job.id, { scanType: e.target.value })}
                    className="w-full px-2 py-2 rounded-sm bg-gray-700 border border-gray-600 text-gray-100 text-sm"
                  >
                    {SCAN_TYPES.map((scanType) => (
                      <option key={scanType} value={scanType}>{scanType}</option>
                    ))}
                  </select>
                </div>
                <div className="lg:col-span-3">
                  <label className="block text-xs text-gray-400 mb-1">Network</label>
                  <select
                    value={SCAN_NETWORKS.some((n) => n.cidr === job.targetNetwork) ? job.targetNetwork : 'custom'}
                    onChange={(e) => {
                      if (e.target.value !== 'custom') {
                        updateJob(job.id, { targetNetwork: e.target.value })
                      }
                    }}
                    className="w-full px-2 py-2 rounded-sm bg-gray-700 border border-gray-600 text-gray-100 text-sm"
                  >
                    {SCAN_NETWORKS.map((network) => (
                      <option key={network.cidr} value={network.cidr}>{network.label}</option>
                    ))}
                    <option value="custom">Custom...</option>
                  </select>
                  {!SCAN_NETWORKS.some((n) => n.cidr === job.targetNetwork) && (
                    <input
                      className="mt-1 w-full px-2 py-1.5 rounded-sm bg-gray-700 border border-gray-600 text-gray-100 text-xs font-mono"
                      value={job.targetNetwork}
                      onChange={(e) => updateJob(job.id, { targetNetwork: e.target.value })}
                    />
                  )}
                </div>
                <div className="lg:col-span-2">
                  <label className="block text-xs text-gray-400 mb-1">Frequency</label>
                  <select
                    value={frequencyFromJob(job)}
                    onChange={(e) => updateJob(job.id, applyFrequency(job, e.target.value))}
                    className="w-full px-2 py-2 rounded-sm bg-gray-700 border border-gray-600 text-gray-100 text-sm"
                  >
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div className="lg:col-span-2">
                  <label className="block text-xs text-gray-400 mb-1">Time</label>
                  <input
                    type="time"
                    value={cronToTime(job)}
                    onChange={(e) => updateJob(job.id, applyTimeToJob(job, e.target.value))}
                    className="w-full px-2 py-2 rounded-sm bg-gray-700 border border-gray-600 text-gray-100 text-sm"
                  />
                </div>
                <div className="lg:col-span-2 flex items-center justify-between gap-2">
                  <div className="text-xs text-gray-400">
                    Next: <span className="text-gray-200">{formatNextRun(job.nextRunTime)}</span>
                  </div>
                  <button
                    type="button"
                    title="Delete job"
                    onClick={() => removeJob(job.id)}
                    className="p-2 text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section icon={Radar} title="Hunter Timers">
        <p className="text-sm text-gray-400">
          Systemd timers that run inventory and assess missions in the background. Changing schedule requires host privileges.
        </p>
        <div className="space-y-3">
          {timers.map((timer) => (
            <div
              key={timer.name}
              className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between bg-gray-900/40 border border-gray-700/60 rounded-md p-4"
            >
              <div>
                <div className="text-gray-100 font-medium">{timer.label}</div>
                <div className="text-xs text-gray-400">{timer.description}</div>
                <div className="text-xs text-gray-500 font-mono mt-1">{timer.unit}</div>
                <div className="text-xs text-gray-400 mt-1">
                  Calendar: {timer.onCalendar || '-'} | State: {timer.activeState}/{timer.unitFileState}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="time"
                  value={timer.time || '02:00'}
                  onChange={(e) => patchTimer(timer.name, { time: e.target.value })}
                  className="px-2 py-1.5 rounded-sm bg-gray-700 border border-gray-600 text-gray-100 text-sm"
                />
                <Toggle
                  checked={!!timer.enabled}
                  onChange={(checked) => patchTimer(timer.name, { enabled: checked })}
                />
              </div>
            </div>
          ))}
          {timers.length === 0 && (
            <p className="text-sm text-gray-500">No hunter timer status available. systemctl may be unavailable.</p>
          )}
        </div>
      </Section>

      <Section icon={Crosshair} title="Pivot / On-demand">
        <div className="bg-gray-900/40 border border-gray-700/60 rounded-md p-4">
          <p className="text-gray-200 font-medium">Pivot missions</p>
          <p className="text-sm text-gray-400 mt-1">
            Pivots are not scheduled. They are spawned on demand from insights. Completed pivot runs appear under Hunter Runs,
            not as nmap Scan History rows unless a handoff scan fires.
          </p>
          <Link to="/hunter-runs" className="inline-block mt-3 text-sm text-blue-400 hover:underline">
            Open Hunter Runs
          </Link>
        </div>
      </Section>

      <Section icon={Wrench} title="Maintenance">
        {maintenance.length === 0 ? (
          <p className="text-sm text-gray-500">No maintenance jobs registered. The scheduler may be disabled in this process.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="py-2 pr-4">Job</th>
                  <th className="py-2 pr-4">Trigger</th>
                  <th className="py-2">Next run</th>
                </tr>
              </thead>
              <tbody>
                {maintenance.map((job) => (
                  <tr key={job.id} className="border-b border-gray-800 text-gray-200">
                    <td className="py-2 pr-4 font-mono text-xs">{job.id}</td>
                    <td className="py-2 pr-4 text-gray-400">{job.trigger || '-'}</td>
                    <td className="py-2">{formatNextRun(job.nextRunTime)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  )
}

export default Schedules
