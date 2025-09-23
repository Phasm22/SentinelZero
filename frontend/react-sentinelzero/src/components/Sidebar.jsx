import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { navigation } from './navigation'

const Sidebar = () => {
  const location = useLocation()
  return (
    <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-56 lg:flex-col z-30" data-testid="desktop-sidebar">
      <div className="flex flex-col flex-grow bg-transparent pt-10" data-testid="sidebar-content">
        <nav className="flex-1 space-y-2 px-4" data-testid="sidebar-navigation">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`group flex items-center px-3 py-3 text-lg font-semibold rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-blue-500/20 text-blue-100 dark:bg-blue-500/20 dark:text-blue-100 shadow-lg shadow-blue-500/20 border border-blue-400/30'
                    : 'text-gray-300 hover:bg-gray-700/50 hover:text-white dark:text-gray-300 dark:hover:bg-gray-700/50 dark:hover:text-white border border-transparent hover:border-gray-600/30'
                }`}
                data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <item.icon className="mr-3 h-6 w-6" data-testid={`nav-icon-${item.name.toLowerCase().replace(/\s+/g, '-')}`} />
                <span data-testid={`nav-text-${item.name.toLowerCase().replace(/\s+/g, '-')}`}>{item.name}</span>
              </Link>
            )
          })}
        </nav>
      </div>
    </div>
  )
}

export default Sidebar 