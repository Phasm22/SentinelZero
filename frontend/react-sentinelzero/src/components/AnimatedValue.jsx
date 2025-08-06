import React, { useEffect, useRef, useState } from 'react'

const AnimatedValue = ({ value, className = '', suffix = '' }) => {
  const [displayValue, setDisplayValue] = useState(0)
  const rafRef = useRef()

  useEffect(() => {
    // Handle null, undefined, NaN values more robustly
    const numericValue = Number(value)
    if (!Number.isFinite(numericValue) || isNaN(numericValue)) {
      setDisplayValue(0)
      return
    }

    let start = Number.isFinite(displayValue) ? displayValue : 0
    let end = numericValue
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
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
    }
    // eslint-disable-next-line
  }, [value])

  return <span className={className}>{Number.isFinite(displayValue) ? displayValue : 0}{suffix}</span>
}

export default AnimatedValue 