import React from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import useModalEscape from '../hooks/useModalEscape'

const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
  showCloseButton = true,
  closeOnOverlayClick = true,
}) => {
  useModalEscape(isOpen, onClose)

  if (!isOpen) return null

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-full mx-4',
  }

  return createPortal(
    <div className="fixed inset-0 z-50 overflow-y-auto" data-testid="modal-container">
      <div
        className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm transition-opacity"
        onClick={closeOnOverlayClick ? onClose : undefined}
        data-testid="modal-backdrop"
        aria-hidden="true"
      />

      <div
        className="flex min-h-full items-center justify-center p-4"
        data-testid="modal-wrapper"
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'modal-title' : undefined}
      >
        <div
          className={`relative w-full ${sizes[size]} transform rounded-lg card-glass shadow-2xl transition-all`}
          data-testid="modal-content"
          onClick={(e) => e.stopPropagation()}
        >
          {title && (
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 dark:border-gray-700" data-testid="modal-header">
              <h3 id="modal-title" className="text-lg font-semibold text-gray-100 font-title" data-testid="modal-title">
                {title}
              </h3>
              {showCloseButton && (
                <button
                  type="button"
                  onClick={onClose}
                  className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                  data-testid="modal-close-btn"
                  aria-label="Close"
                >
                  <X className="h-5 w-5" />
                </button>
              )}
            </div>
          )}

          <div className="px-6 py-4 font-sans font-normal" data-testid="modal-body">
            {children}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

export default Modal
