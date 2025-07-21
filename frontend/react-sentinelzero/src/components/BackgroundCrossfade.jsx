import React, { useEffect, useState } from 'react'

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

function getMode() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}
function getDevice() {
  return window.innerWidth <= 768 ? 'mobile' : 'desktop'
}

const BackgroundCrossfade = () => {
  const [currentBg, setCurrentBg] = useState(() => backgrounds[getMode()][getDevice()])
  const [nextBg, setNextBg] = useState(null)
  const [isTransitioning, setIsTransitioning] = useState(false)

  useEffect(() => {
    function updateBg() {
      const newBg = backgrounds[getMode()][getDevice()]
      if (newBg !== currentBg && !isTransitioning) {
        setNextBg(newBg)
        setIsTransitioning(true)
        setTimeout(() => {
          setCurrentBg(newBg)
          setNextBg(null)
          setIsTransitioning(false)
        }, 600)
      }
    }
    window.addEventListener('resize', updateBg)
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateBg)
    return () => {
      window.removeEventListener('resize', updateBg)
      window.matchMedia('(prefers-color-scheme: dark)').removeEventListener('change', updateBg)
    }
  }, [currentBg, isTransitioning])

  return (
    <>
      {/* Current background layer */}
      <div
        style={{
          backgroundImage: `url(${currentBg})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          backgroundColor: getMode() === 'dark' ? '#0f0f0f' : '#18181b',
          opacity: isTransitioning ? 0 : 1,
          transition: 'opacity 0.6s cubic-bezier(0.4,0,0.2,1)',
          position: 'fixed',
          inset: 0,
          zIndex: -2,
          pointerEvents: 'none',
        }}
        aria-hidden="true"
      />
      {/* Next background layer (only during transition) */}
      {nextBg && isTransitioning && (
        <div
          style={{
            backgroundImage: `url(${nextBg})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat',
            backgroundColor: getMode() === 'dark' ? '#0f0f0f' : '#18181b',
            opacity: 1,
            transition: 'opacity 0.6s cubic-bezier(0.4,0,0.2,1)',
            position: 'fixed',
            inset: 0,
            zIndex: -3,
            pointerEvents: 'none',
          }}
          aria-hidden="true"
        />
      )}
    </>
  )
}

export default BackgroundCrossfade 