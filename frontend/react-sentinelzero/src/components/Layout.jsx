import React, { useState } from 'react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'
import { Menu, X } from 'lucide-react'
import Sidebar from './Sidebar'
import SpaceDots from './SpaceDots'
import ConnectionStatus from './ConnectionStatus'
import { useLocation, Link } from 'react-router-dom'
import { navigation } from './navigation'
import { Sun, Moon, Monitor } from 'lucide-react'

const ThemeControls = () => {
  const { preferences, updatePreference } = useUserPreferences()
  const order = ['light', 'dark', 'system']
  const next = () => {
    const idx = order.indexOf(preferences.theme || 'system')
    const nextTheme = order[(idx + 1) % order.length]
    updatePreference('theme', nextTheme)
  }
  const iconMap = {
    light: <Sun className="h-4 w-4" />,
    dark: <Moon className="h-4 w-4" />,
    system: <Monitor className="h-4 w-4" />,
  }
  return (
    <div className="flex items-center flex-shrink-0 gap-2" data-testid="theme-controls">
      <button
        type="button"
        onClick={next}
        className="flex items-center gap-1 px-3 py-1 rounded-md text-xs font-semibold bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 border border-gray-300 dark:border-gray-600 shadow hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
        title={`Theme: ${preferences.theme} (click to cycle)`}
        data-testid="theme-toggle-btn"
      >
        {iconMap[preferences.theme]}
        <span className="capitalize" data-testid="theme-text">{preferences.theme}</span>
      </button>
      <ConnectionStatus />
    </div>
  )
}

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="min-h-screen w-full" data-testid="layout-container">
      {/* Space dots overlay */}
      <SpaceDots />
      {/* Main content (sidebar + main) */}
      <div className="relative z-10 flex w-full min-h-screen" data-testid="main-layout">
        {/* Sidebar - even narrower */}
        <div className="w-40 flex-shrink-0 h-full fixed top-0 left-0 z-20 hidden lg:block" data-testid="desktop-sidebar">
          <Sidebar navigation={navigation} />
        </div>
        {/* Main content area - maximum width */}
        <div className="flex flex-col min-h-screen lg:ml-40 w-full" data-testid="main-content-area">
          {/* Custom header - minimal padding */}
          <header className="flex flex-wrap items-center justify-between gap-2 sm:gap-4 px-2 py-2 w-full" data-testid="main-header">
            <div className="flex items-center gap-4" data-testid="header-left">
              <button
                type="button"
                className="lg:hidden text-gray-700 dark:text-gray-200 focus:outline-none"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
                data-testid="open-sidebar-btn"
              >
                <Menu className="h-8 w-8" />
              </button>
              <div className="flex items-center gap-3" data-testid="brand-section">
                {/* Logo placeholder */}
                <div className="w-12 h-12 bg-transparent flex items-center justify-center" data-testid="logo-container">
                  {/* Replace this div with your logo image */}
                  <img src="/favicon.png" alt="SentinelZero" className="w-full h-full object-contain" data-testid="logo-image" />
                  {/* <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-lg">S</span>
                  </div> */}
                </div>
                <h1 className="text-4xl md:text-5xl font-title font-extrabold tracking-tight text-gray-900 dark:text-white leading-tight" data-testid="main-header-title">
                  SentinelZero
                </h1>
              </div>
            </div>
            <div data-testid="header-right">
              <ThemeControls />
            </div>
          </header>
          <main className="flex-1 w-full px-2 pb-2" data-testid="main-content">
            {children}
          </main>
        </div>
      </div>
      {/* Mobile sidebar with animation */}
      <div className={`fixed inset-0 z-50 lg:hidden pointer-events-none`} data-testid="mobile-sidebar-overlay">
        {/* Overlay fade */}
        <div
          className={`absolute inset-0 bg-black/60 transition-opacity duration-500 ease-in-out ${sidebarOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
          onClick={() => setSidebarOpen(false)}
          data-testid="sidebar-backdrop"
        />
        {/* Sidebar slide-in */}
        <aside
          className={`absolute inset-y-0 left-0 w-72 max-w-full bg-gray-900/95 backdrop-blur-lg border-r border-white/10 dark:border-gray-800 pt-8 shadow-2xl transform transition-transform duration-500 ease-in-out ${sidebarOpen ? 'translate-x-0 pointer-events-auto' : '-translate-x-full pointer-events-none'}`}
          aria-label="Sidebar"
          data-testid="mobile-sidebar"
        >
          <button
            className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors duration-200"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
            data-testid="close-sidebar-btn"
          >
            <X className="h-7 w-7" />
          </button>
          <nav className="flex-1 space-y-2 px-4 mt-8" data-testid="mobile-navigation">
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
                  data-testid={`mobile-nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
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