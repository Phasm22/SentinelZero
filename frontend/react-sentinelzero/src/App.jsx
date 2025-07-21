import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { SocketProvider } from './contexts/SocketContext'
import { ToastProvider } from './contexts/ToastContext'
import { UserPreferencesProvider } from './contexts/UserPreferencesContext'
import Dashboard from './pages/Dashboard'
import ScanHistory from './pages/ScanHistory'
import Settings from './pages/Settings'
import Layout from './components/Layout'
import BackgroundCrossfade from './components/BackgroundCrossfade'
import './App.css'

function App() {
  console.log('App loaded')
  return (
    <Router>
      <SocketProvider>
        <ToastProvider>
          <UserPreferencesProvider>
            <BackgroundCrossfade />
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/scan-history" element={<ScanHistory />} />
                <Route path="/settings" element={<Settings />} />
                {/* Fallback route for unmatched paths */}
                <Route path="*" element={<div className="p-8 text-center text-red-600">404: Page Not Found</div>} />
              </Routes>
            </Layout>
          </UserPreferencesProvider>
        </ToastProvider>
      </SocketProvider>
    </Router>
  )
}

export default App 