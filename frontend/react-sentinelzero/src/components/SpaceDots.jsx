import React, { useState } from 'react'

const SpaceDots = () => {
  const DOT_COUNT = 32
  const [dots] = useState(() => {
    return Array.from({ length: DOT_COUNT }, (_, i) => ({
      top: Math.random() * 100,
      left: Math.random() * 100,
      size: 2 + Math.random() * 2,
      opacity: 0.12 + Math.random() * 0.18,
    }))
  })
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-10"
      style={{ width: '100vw', height: '100vh' }}
    >
      {dots.map((dot, i) => (
        <span
          key={i}
          style={{
            position: 'absolute',
            top: `${dot.top}%`,
            left: `${dot.left}%`,
            width: dot.size,
            height: dot.size,
            borderRadius: '50%',
            background: 'white',
            opacity: dot.opacity,
            boxShadow: '0 0 6px 1px white',
            pointerEvents: 'none',
            filter: 'blur(0.5px)',
            transition: 'opacity 0.7s',
          }}
        />
      ))}
    </div>
  )
}

export default SpaceDots 