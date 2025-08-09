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
    // Theme handling
    const root = document.documentElement
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const wantDark = preferences.theme === 'dark' || (preferences.theme === 'system' && systemDark)
    root.classList.toggle('dark', wantDark)
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