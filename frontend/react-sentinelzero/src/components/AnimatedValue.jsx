import React, { useEffect, useRef, useState } from 'react'

const AnimatedValue = ({ value, className = '' }) => {
  const [displayValue, setDisplayValue] = useState(0)
  const rafRef = useRef()

  useEffect(() => {
    let start = displayValue
    let end = Number(value)
    let startTime = null
    const duration = 700

    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      const current = Math.round(start + (end - start) * progress)
      setDisplayValue(current)
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate)
      }
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(rafRef.current)
    // eslint-disable-next-line
  }, [value])

  return <span className={className}>{displayValue}</span>
}

export default AnimatedValue 