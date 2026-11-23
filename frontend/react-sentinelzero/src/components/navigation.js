import { LayoutDashboard, History, Activity, Settings, Radar, Clock } from 'lucide-react'

export const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Scan History', href: '/scan-history', icon: History },
  { name: 'Hunter Runs', href: '/hunter-runs', icon: Radar },
  { name: 'Lab Status', href: '/lab-status', icon: Activity },
  { name: 'Schedules', href: '/schedules', icon: Clock },
  { name: 'Settings', href: '/settings', icon: Settings },
]
