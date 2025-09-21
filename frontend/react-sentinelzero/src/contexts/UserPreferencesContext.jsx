import React, { createContext, useContext, useState, useEffect } from 'react'

const UserPreferencesContext = createContext()

export const useUserPreferences = () => useContext(UserPreferencesContext)

export const UserPreferencesProvider = ({ children }) => {
  const [preferences, setPreferences] = useState({ use24Hour: false, theme: 'system' })

  useEffect(() => {
    const stored = localStorage.getItem('userPreferences')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        setPreferences(parsed)
        console.log('Loaded preferences from localStorage:', parsed)
      } catch (error) {
        console.error('Error parsing stored preferences:', error)
      }
    }
  }, [])

  useEffect(() => {
    localStorage.setItem('userPreferences', JSON.stringify(preferences))
    const root = document.documentElement
    const mq = window.matchMedia('(prefers-color-scheme: dark)')

    const apply = () => {
      const systemDark = mq.matches
      const wantDark = preferences.theme === 'dark' || (preferences.theme === 'system' && systemDark)
      console.log('Applying theme:', { 
        theme: preferences.theme, 
        systemDark, 
        wantDark,
        currentClasses: root.className,
        timestamp: new Date().toISOString()
      })
      
      if (wantDark) {
        root.classList.add('dark')
        console.log('Added dark class')
      } else {
        root.classList.remove('dark')
        console.log('Removed dark class')
      }
      
      // Force a re-render by dispatching a custom event
      window.dispatchEvent(new CustomEvent('themeChanged', { 
        detail: { theme: preferences.theme, systemDark, wantDark } 
      }))
    }

    apply()

    // Always listen for system changes, but only apply if theme is 'system'
    const handleSystemThemeChange = (e) => {
      console.log('System theme change detected:', e.matches)
      if (preferences.theme === 'system') {
        console.log('Applying system theme change')
        apply()
      }
    }

    if (mq.addEventListener) {
      mq.addEventListener('change', handleSystemThemeChange)
      return () => mq.removeEventListener('change', handleSystemThemeChange)
    } else if (mq.addListener) {
      mq.addListener(handleSystemThemeChange)
      return () => mq.removeListener(handleSystemThemeChange)
    }
  }, [preferences])

  const updatePreference = (key, value) => {
    setPreferences(prev => ({ ...prev, [key]: value }))
  }

  return (
    <UserPreferencesContext.Provider value={{ preferences, updatePreference }}>
      {children}
    </UserPreferencesContext.Provider>
  )
} 