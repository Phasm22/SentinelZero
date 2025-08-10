import React, { useEffect, useState, useRef } from 'react'
import { useUserPreferences } from '../contexts/UserPreferencesContext'

const backgrounds = {
  light: {
    desktop: '/backgrounds/blob-desk-light.png',
    mobile: '/backgrounds/blob-mobile-light.png',
  },
  dark: {
    desktop: '/backgrounds/blob-desk-dark.png',
    mobile: '/backgrounds/blob-mobile-dark.png',
  },
}

function deriveDevice() { return window.innerWidth <= 768 ? 'mobile' : 'desktop' }

const BackgroundCrossfade = () => {
  // Always start with light (requested) then transition if dark preferred
  const [currentBg, setCurrentBg] = useState(() => backgrounds.light[deriveDevice()])
  const [transitionBg, setTransitionBg] = useState(null)
  const [isTransitioning, setIsTransitioning] = useState(false)
  const transitionTimeoutRef = useRef(null)
  const { preferences } = useUserPreferences()

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')

    const computeWantDark = () => {
      if (preferences.theme === 'dark') return true
      if (preferences.theme === 'light') return false
      // 'system'
      return mq.matches
    }

    const performTransition = (target) => {
      if (isTransitioning || target === currentBg) return
      // Preload target first (Firefox sometimes delays paint until load started)
      const img = new Image()
      img.src = target
      setTransitionBg(target)
      setIsTransitioning(true)
      // After CSS transition (~600ms) finalize
      transitionTimeoutRef.current = window.setTimeout(() => {
        setCurrentBg(target)
        setTransitionBg(null)
        setIsTransitioning(false)
      }, 620)
    }

    const reconcile = (reason='update') => {
      const wantDark = computeWantDark()
      const device = deriveDevice()
      const desired = wantDark ? backgrounds.dark[device] : backgrounds.light[device]
      if (desired !== currentBg) {
        // eslint-disable-next-line no-console
        console.log('[BackgroundCrossfade]', reason, { wantDark, desired })
        performTransition(desired)
      }
    }

    // Initial checks (RAF + slight delay for Firefox)
  requestAnimationFrame(() => reconcile('initial-rAF'))
  setTimeout(() => reconcile('initial-timeout'), 120)

    const resizeHandler = () => reconcile('resize')
    window.addEventListener('resize', resizeHandler)

    const mqHandler = () => reconcile('media-query')
    if (mq.addEventListener) mq.addEventListener('change', mqHandler)
    else if (mq.addListener) mq.addListener(mqHandler)

    const observer = new MutationObserver(muts => {
      for (const m of muts) {
        if (m.attributeName === 'class') { reconcile('html-class'); break }
      }
    })
    observer.observe(document.documentElement, { attributes: true })

    return () => {
      if (transitionTimeoutRef.current) clearTimeout(transitionTimeoutRef.current)
      window.removeEventListener('resize', resizeHandler)
      if (mq.removeEventListener) mq.removeEventListener('change', mqHandler)
      else if (mq.removeListener) mq.removeListener(mqHandler)
      observer.disconnect()
    }
  }, [currentBg, isTransitioning, preferences.theme])

  return (
    <>
      {/* Base (current) layer */}
      <div
        style={{
          backgroundImage: `url(${currentBg})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          backgroundColor: '#18181b',
          opacity: 1,
          position: 'fixed',
          inset: 0,
          zIndex: -3,
          pointerEvents: 'none',
        }}
        aria-hidden="true"
      />
      {/* Transition overlay */}
      {transitionBg && (
        <div
          style={{
            backgroundImage: `url(${transitionBg})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat',
            backgroundColor: '#0f0f0f',
            opacity: isTransitioning ? 1 : 0,
            transition: 'opacity 0.6s cubic-bezier(0.4,0,0.2,1)',
            position: 'fixed',
            inset: 0,
            zIndex: -2,
            pointerEvents: 'none',
          }}
          aria-hidden="true"
        />
      )}
    </>
  )
}

export default BackgroundCrossfade 