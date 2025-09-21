import React, { useState, useEffect } from 'react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'

const ThemeTest = () => {
  const { preferences, updatePreference } = useUserPreferences()
  const [systemTheme, setSystemTheme] = useState('unknown')
  const [htmlClasses, setHtmlClasses] = useState('')

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    setSystemTheme(mq.matches ? 'dark' : 'light')
    setHtmlClasses(document.documentElement.className)

    const handleChange = (e) => {
      setSystemTheme(e.matches ? 'dark' : 'light')
      setHtmlClasses(document.documentElement.className)
    }

    if (mq.addEventListener) {
      mq.addEventListener('change', handleChange)
      return () => mq.removeEventListener('change', handleChange)
    } else if (mq.addListener) {
      mq.addListener(handleChange)
      return () => mq.removeListener(handleChange)
    }
  }, [])

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setHtmlClasses(document.documentElement.className)
    })
    observer.observe(document.documentElement, { attributes: true })
    
    const handleThemeChange = () => {
      setHtmlClasses(document.documentElement.className)
    }
    
    window.addEventListener('themeChanged', handleThemeChange)
    
    return () => {
      observer.disconnect()
      window.removeEventListener('themeChanged', handleThemeChange)
    }
  }, [])

  return (
    <div className="min-h-screen p-8 bg-white dark:bg-gray-900 text-gray-900 dark:text-white transition-colors">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Theme Test Page</h1>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Theme Controls */}
          <div className="bg-gray-100 dark:bg-gray-800 p-6 rounded-lg">
            <h2 className="text-xl font-semibold mb-4">Theme Controls</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Theme Preference:</label>
                <select
                  value={preferences.theme}
                  onChange={(e) => updatePreference('theme', e.target.value)}
                  className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="system">System</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </div>
              
              <div className="space-y-2">
                <button
                  onClick={() => updatePreference('theme', 'light')}
                  className="w-full p-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
                >
                  Force Light
                </button>
                <button
                  onClick={() => updatePreference('theme', 'dark')}
                  className="w-full p-2 bg-gray-800 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  Force Dark
                </button>
                <button
                  onClick={() => updatePreference('theme', 'system')}
                  className="w-full p-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors"
                >
                  Use System
                </button>
              </div>
            </div>
          </div>

          {/* Theme Status */}
          <div className="bg-gray-100 dark:bg-gray-800 p-6 rounded-lg">
            <h2 className="text-xl font-semibold mb-4">Current Status</h2>
            <div className="space-y-2 text-sm">
              <div><strong>User Preference:</strong> {preferences.theme}</div>
              <div><strong>System Theme:</strong> {systemTheme}</div>
              <div><strong>HTML Classes:</strong> {htmlClasses || 'none'}</div>
              <div><strong>Has Dark Class:</strong> {htmlClasses.includes('dark') ? 'Yes' : 'No'}</div>
              <div><strong>Should be Dark:</strong> {
                preferences.theme === 'dark' || (preferences.theme === 'system' && systemTheme === 'dark') ? 'Yes' : 'No'
              }</div>
            </div>
          </div>
        </div>

        {/* Visual Test */}
        <div className="mt-8 bg-gray-100 dark:bg-gray-800 p-6 rounded-lg">
          <h2 className="text-xl font-semibold mb-4">Visual Test</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white dark:bg-gray-700 p-4 rounded border border-gray-200 dark:border-gray-600">
              <h3 className="font-semibold text-gray-900 dark:text-white">Card 1</h3>
              <p className="text-gray-600 dark:text-gray-300">This should change color with theme</p>
            </div>
            <div className="bg-blue-100 dark:bg-blue-900 p-4 rounded border border-blue-200 dark:border-blue-700">
              <h3 className="font-semibold text-blue-900 dark:text-blue-100">Card 2</h3>
              <p className="text-blue-700 dark:text-blue-300">Blue themed card</p>
            </div>
            <div className="bg-green-100 dark:bg-green-900 p-4 rounded border border-green-200 dark:border-green-700">
              <h3 className="font-semibold text-green-900 dark:text-green-100">Card 3</h3>
              <p className="text-green-700 dark:text-green-300">Green themed card</p>
            </div>
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-8 bg-yellow-100 dark:bg-yellow-900 p-6 rounded-lg border border-yellow-200 dark:border-yellow-700">
          <h2 className="text-xl font-semibold mb-4 text-yellow-800 dark:text-yellow-200">Test Instructions</h2>
          <ol className="list-decimal list-inside space-y-2 text-yellow-700 dark:text-yellow-300">
            <li>Set theme to "System" and toggle your macOS system theme (System Preferences → General → Appearance)</li>
            <li>Watch the "System Theme" value change and the page colors should update automatically</li>
            <li>Try setting theme to "Light" or "Dark" to override system preference</li>
            <li>Check the browser console for theme change logs</li>
          </ol>
        </div>
      </div>
    </div>
  )
}

export default ThemeTest
