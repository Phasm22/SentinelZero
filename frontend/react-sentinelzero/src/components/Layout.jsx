import React, { useState, useEffect, useRef } from 'react'
import { Menu, X, LayoutDashboard, History, Settings as SettingsIcon } from 'lucide-react'
import Sidebar from './Sidebar'
import SpaceDots from './SpaceDots'
import { useLocation, Link } from 'react-router-dom'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Scan History', href: '/scan-history', icon: History },
  { name: 'Settings', href: '/settings', icon: SettingsIcon },
]

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="min-h-screen w-screen flex relative overflow-hidden">
      {/* Full viewport background layer */}
      <div
        aria-hidden="true"
        className="fixed inset-0 z-0"
        style={{
          background: `linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%)`,
          backgroundImage: `url('/backgrounds/blob-desk-dark.png')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      />
      {/* Space dots overlay */}
      <SpaceDots />
      {/* Main content (sidebar + main) */}
      <div className="relative z-10 flex w-full min-h-screen">
        {/* Sidebar flush left, no margin/padding */}
        <div className="w-64 flex-shrink-0 h-full fixed top-0 left-0 z-20 hidden lg:block">
          <Sidebar navigation={navigation} />
        </div>
        {/* Main content area, responsive and centered */}
        <div className="flex flex-col min-h-screen lg:ml-64 max-w-screen-xl mx-auto px-6">
          {/* Custom header */}
          <header className="flex items-center gap-4 px-6 py-6 md:py-8 w-full">
            <button
              type="button"
              className="lg:hidden text-gray-700 dark:text-gray-200 focus:outline-none"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open sidebar"
            >
              <Menu className="h-8 w-8" />
            </button>
            <h1 className="text-4xl md:text-5xl font-title font-extrabold tracking-tight text-gray-900 dark:text-white leading-tight">
              SentinelZero
            </h1>
          </header>
          <main className="flex-1 w-full px-2 sm:px-4 lg:px-8 space-y-10">
            {children}
          </main>
        </div>
      </div>
      {/* Mobile sidebar with animation */}
      <div className={`fixed inset-0 z-50 lg:hidden pointer-events-none`}>
        {/* Overlay fade */}
        <div
          className={`absolute inset-0 bg-black/60 transition-opacity duration-500 ease-in-out ${sidebarOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
          onClick={() => setSidebarOpen(false)}
        />
        {/* Sidebar slide-in */}
        <aside
          className={`absolute inset-y-0 left-0 w-72 max-w-full bg-gray-900/95 backdrop-blur-lg border-r border-white/10 dark:border-gray-800 pt-8 shadow-2xl transform transition-transform duration-500 ease-in-out ${sidebarOpen ? 'translate-x-0 pointer-events-auto' : '-translate-x-full pointer-events-none'}`}
          aria-label="Sidebar"
        >
          <button
            className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors duration-200"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <X className="h-7 w-7" />
          </button>
          <nav className="flex-1 space-y-2 px-4 mt-8">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
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
        </aside>
      </div>
    </div>
  )
}

export default Layout 