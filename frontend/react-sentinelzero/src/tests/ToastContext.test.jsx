import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { renderToString } from 'react-dom/server'
import userEvent from '@testing-library/user-event'
import { ToastProvider, useToast } from '../contexts/ToastContext'

function ToastConsumer() {
  const { showToast } = useToast()
  return (
    <button type="button" onClick={() => showToast('Hello toast', 'success')}>
      Show Toast
    </button>
  )
}

describe('ToastContext', () => {
  it('shows and renders toast messages', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )

    await user.click(screen.getByRole('button', { name: /show toast/i }))
    expect(screen.getByText('Hello toast')).toBeInTheDocument()
  })

  it('throws when useToast is used outside provider', () => {
    const Broken = () => {
      useToast()
      return null
    }

    expect(() => renderToString(<Broken />)).toThrow(/ToastProvider/)
  })
})
