import { useState, useCallback, useEffect } from 'react'

const STORAGE_KEY = 'sentinelzero:viewed-scans'

function readViewedIds() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    return new Set(Array.isArray(parsed) ? parsed : [])
  } catch {
    return new Set()
  }
}

function writeViewedIds(ids) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]))
  } catch {
    // ignore quota / private mode
  }
}

export default function useViewedScans() {
  const [viewedIds, setViewedIds] = useState(() => readViewedIds())

  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === STORAGE_KEY) {
        setViewedIds(readViewedIds())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const isViewed = useCallback(
    (scanId) => viewedIds.has(scanId),
    [viewedIds],
  )

  const markViewed = useCallback((scanId) => {
    if (scanId == null) return
    setViewedIds((prev) => {
      if (prev.has(scanId)) return prev
      const next = new Set(prev)
      next.add(scanId)
      writeViewedIds(next)
      return next
    })
  }, [])

  return { isViewed, markViewed }
}
