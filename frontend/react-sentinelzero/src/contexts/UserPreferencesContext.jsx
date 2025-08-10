import React, { createContext, useContext, useState, useEffect } from 'react'

const UserPreferencesContext = createContext()

export const useUserPreferences = () => useContext(UserPreferencesContext)

export const UserPreferencesProvider = ({ children }) => {
  const [preferences, setPreferences] = useState({ use24Hour: false, theme: 'system' })

  useEffect(() => {
    const stored = localStorage.getItem('userPreferences')
    if (stored) {
      setPreferences(JSON.parse(stored))
    }
  }, [])

  useEffect(() => {
    localStorage.setItem('userPreferences', JSON.stringify(preferences))
    const root = document.documentElement
    const mq = window.matchMedia('(prefers-color-scheme: dark)')

    const apply = () => {
      const systemDark = mq.matches
      const wantDark = preferences.theme === 'dark' || (preferences.theme === 'system' && systemDark)
      root.classList.toggle('dark', wantDark)
    }

    apply()

    // While in 'system' mode keep listening for OS changes; otherwise no listener needed.
    if (preferences.theme === 'system') {
      if (mq.addEventListener) {
        mq.addEventListener('change', apply)
      } else if (mq.addListener) {
        mq.addListener(apply)
      }
      return () => {
        if (mq.removeEventListener) {
          mq.removeEventListener('change', apply)
        } else if (mq.removeListener) {
          mq.removeListener(apply)
        }
      }
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