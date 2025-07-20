import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, 
  History, 
  Settings as SettingsIcon,
  Menu,
  X
} from 'lucide-react'

const getBackgroundImage = () => {
  const isMobile = window.matchMedia('(max-width: 768px)').matches
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  if (isMobile && isDark) return '/backgrounds/blob-mobile-dark.png'
  if (isMobile && !isDark) return '/backgrounds/blob-mobile-light.png'
  if (!isMobile && isDark) return '/backgrounds/blob-desk-dark.png'
  return '/backgrounds/blob-desk-light.png'
}

// Scattered space dots overlay
const SpaceDots = () => {
  // Fewer dots for subtlety
  const DOT_COUNT = 32
  // Use a fixed seed for consistent scatter on each render
  const [dots] = useState(() => {
    return Array.from({ length: DOT_COUNT }, (_, i) => ({
      top: Math.random() * 100,
      left: Math.random() * 100,
      size: 2 + Math.random() * 2, // 2-4px
      opacity: 0.12 + Math.random() * 0.18, // 0.12-0.3
    }))
  })
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-10"
      style={{
        width: '100vw',
        height: '100vh',
      }}
    >
      {dots.map((dot, i) => (
        <span
          key={i}
          style={{
            position: 'absolute',
            top: `${dot.top}%`,
            left: `${dot.left}%`,
            width: dot.size,
            height: dot.size,
            borderRadius: '50%',
            background: 'white',
            opacity: dot.opacity,
            boxShadow: '0 0 6px 1px white',
            pointerEvents: 'none',
            filter: 'blur(0.5px)',
            transition: 'opacity 0.7s',
          }}
        />
      ))}
    </div>
  )
}

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const [background, setBackground] = useState(getBackgroundImage())

  useEffect(() => {
    const updateBackground = () => setBackground(getBackgroundImage())
    const mqDark = window.matchMedia('(prefers-color-scheme: dark)')
    const mqMobile = window.matchMedia('(max-width: 768px)')
    mqDark.addEventListener('change', updateBackground)
    mqMobile.addEventListener('change', updateBackground)
    window.addEventListener('resize', updateBackground)
    return () => {
      mqDark.removeEventListener('change', updateBackground)
      mqMobile.removeEventListener('change', updateBackground)
      window.removeEventListener('resize', updateBackground)
    }
  }, [])

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Scan History', href: '/scan-history', icon: History },
    { name: 'Settings', href: '/settings', icon: SettingsIcon },
  ]

  return (
    <div className="min-h-screen relative">
      {/* Background image layer */}
      <div
        aria-hidden="true"
        className="fixed inset-0 z-0 transition-all duration-700 bg-cover bg-center"
        style={{
          backgroundImage: `url(${background})`,
          transition: 'background-image 0.7s cubic-bezier(0.4,0,0.2,1)',
        }}
      />
      {/* Space dots overlay */}
      <SpaceDots />
      {/* Overlay for content (keeps existing layout above background) */}
      <div className="relative z-20 min-h-screen bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-sm">
        {/* Mobile sidebar */}
        <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`}>
          <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
          <div className="fixed inset-y-0 left-0 flex w-64 flex-col bg-white dark:bg-gray-800">
            <div className="flex h-16 items-center justify-between px-4">
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">SentinelZero</h1>
              <button
                onClick={() => setSidebarOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            <nav className="flex-1 space-y-1 px-2 py-4">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    onClick={() => setSidebarOpen(false)}
                    className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive
                        ? 'bg-primary-100 text-primary-900 dark:bg-primary-900 dark:text-primary-100'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white'
                    }`}
                  >
                    <item.icon className="mr-3 h-5 w-5" />
                    {item.name}
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>

        {/* Desktop sidebar */}
        <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
          <div className="flex flex-col flex-grow bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700">
            <div className="flex h-16 items-center px-4">
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">SentinelZero</h1>
            </div>
            <nav className="flex-1 space-y-1 px-2 py-4">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive
                        ? 'bg-primary-100 text-primary-900 dark:bg-primary-900 dark:text-primary-100'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white'
                    }`}
                  >
                    <item.icon className="mr-3 h-5 w-5" />
                    {item.name}
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>

        {/* Main content */}
        <div className="lg:pl-64">
          {/* Mobile header */}
          <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 shadow-sm lg:hidden">
            <button
              type="button"
              className="-m-2.5 p-2.5 text-gray-700 dark:text-gray-300 lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-6 w-6" />
            </button>
            <div className="flex-1 text-sm font-semibold leading-6 text-gray-900 dark:text-white">
              SentinelZero
            </div>
          </div>

          {/* Page content */}
          <main className="py-6">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}

export default Layout 