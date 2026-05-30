import { LayoutDashboard, History, Activity, Settings, Radar } from 'lucide-react'

export const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Scan History', href: '/scan-history', icon: History },
  { name: 'Hunter Runs', href: '/hunter-runs', icon: Radar },
  { name: 'Lab Status', href: '/lab-status', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
] 