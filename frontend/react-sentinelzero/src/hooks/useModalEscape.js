import { useEffect } from 'react'

/** Stack of open overlays — Escape closes only the topmost. */
const stack = []

/**
 * Register Escape-to-close and body scroll lock while an overlay is open.
 * @param {boolean} isOpen
 * @param {() => void} onClose
 * @param {{ lockScroll?: boolean }} [options]
 */
export function useModalEscape(isOpen, onClose, options = {}) {
  const { lockScroll = true } = options

  useEffect(() => {
    if (!isOpen || !onClose) return

    const entry = { onClose }
    stack.push(entry)

    const handleKeyDown = (event) => {
      if (event.key !== 'Escape') return
      const top = stack[stack.length - 1]
      if (top !== entry) return
      event.preventDefault()
      event.stopPropagation()
      top.onClose()
    }

    document.addEventListener('keydown', handleKeyDown, true)
    if (lockScroll) {
      document.body.style.overflow = 'hidden'
    }

    return () => {
      const idx = stack.indexOf(entry)
      if (idx !== -1) stack.splice(idx, 1)
      document.removeEventListener('keydown', handleKeyDown, true)
      if (lockScroll && stack.length === 0) {
        document.body.style.overflow = ''
      }
    }
  }, [isOpen, onClose, lockScroll])
}

export default useModalEscape
