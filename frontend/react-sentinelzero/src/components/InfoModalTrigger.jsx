import React, { useState } from 'react'
import { Info } from 'lucide-react'
import Modal from './Modal'

const InfoModalTrigger = ({
  title,
  children,
  ariaLabel = 'More information',
  testId = 'info-modal-trigger',
  className = '',
  iconClassName = 'w-4 h-4',
}) => {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setOpen(true)
        }}
        className={`inline-flex items-center justify-center rounded-full text-gray-400 hover:text-blue-300 hover:bg-white/5 transition-colors p-0.5 ${className}`}
        aria-label={ariaLabel}
        data-testid={testId}
      >
        <Info className={iconClassName} />
      </button>
      <Modal isOpen={open} onClose={() => setOpen(false)} title={title} size="md">
        <div className="text-sm text-gray-300 space-y-3 leading-relaxed">{children}</div>
      </Modal>
    </>
  )
}

export default InfoModalTrigger
