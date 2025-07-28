import { LayoutDashboard, History, Activity, Settings } from 'lucide-react'

export const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Scan History', href: '/scan-history', icon: History },
  { name: 'Lab Status', href: '/lab-status', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
] 