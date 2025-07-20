import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, History, Settings as SettingsIcon } from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Scan History', href: '/scan-history', icon: History },
  { name: 'Settings', href: '/settings', icon: SettingsIcon },
]

const Sidebar = () => {
  const location = useLocation()
  return (
    <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col z-30">
      <div className="flex flex-col flex-grow bg-transparent border-r border-white/10 dark:border-gray-800 pt-8">
        <nav className="flex-1 space-y-2 px-4">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`group flex items-center px-3 py-2 text-lg font-semibold rounded-lg transition-colors ${
                  isActive
                    ? 'bg-primary-100 text-primary-900 dark:bg-primary-900 dark:text-primary-100 shadow'
                    : 'text-gray-400 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white'
                }`}
              >
                <item.icon className="mr-3 h-6 w-6" />
                {item.name}
              </Link>
            )
          })}
        </nav>
      </div>
    </div>
  )
}

export default Sidebar 