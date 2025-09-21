import React, { Suspense, lazy } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { SocketProvider } from './contexts/SocketContext'
import { ToastProvider } from './contexts/ToastContext'
// Lazy route chunks
const Dashboard = lazy(() => import('./pages/Dashboard'))
const ScanHistory = lazy(() => import('./pages/ScanHistory'))
const LabStatus = lazy(() => import('./pages/LabStatus'))
const Settings = lazy(() => import('./pages/Settings'))
const ThemeTest = lazy(() => import('./pages/ThemeTest'))
import Layout from './components/Layout'
import BackgroundCrossfade from './components/BackgroundCrossfade'
import './App.css'

function App() {
  console.log('App loaded')
  return (
    <Router>
      <SocketProvider>
        <ToastProvider>
          <BackgroundCrossfade />
          <Layout>
            <Suspense fallback={<div className="p-8 text-center text-gray-400">Loading...</div>}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/scan-history" element={<ScanHistory />} />
                <Route path="/lab-status" element={<LabStatus />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/theme-test" element={<ThemeTest />} />
                <Route path="*" element={<div className="p-8 text-center text-red-600">404: Page Not Found</div>} />
              </Routes>
            </Suspense>
          </Layout>
        </ToastProvider>
      </SocketProvider>
    </Router>
  )
}

export default App 