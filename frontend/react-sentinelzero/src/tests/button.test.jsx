/**
 * Button Component Test Suite
 * Tests the Button component functionality
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Button from '../components/Button'

describe('Button Component', () => {
  it('should render with default props', () => {
    render(<Button>Test Button</Button>)
    
    const button = screen.getByRole('button', { name: /test button/i })
    expect(button).toBeInTheDocument()
    expect(button).toHaveClass('bg-blue-600') // Primary variant
    expect(button).toHaveClass('px-4', 'py-2') // Default size
  })

  it('should render with different variants', () => {
    const { rerender } = render(<Button variant="secondary">Secondary</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-gray-600')

    rerender(<Button variant="danger">Danger</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-red-600')

    rerender(<Button variant="outline">Outline</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-transparent')
  })

  it('should render with different sizes', () => {
    const { rerender } = render(<Button size="sm">Small</Button>)
    expect(screen.getByRole('button')).toHaveClass('px-3', 'py-1.5')

    rerender(<Button size="lg">Large</Button>)
    expect(screen.getByRole('button')).toHaveClass('px-6', 'py-3')

    rerender(<Button size="xl">Extra Large</Button>)
    expect(screen.getByRole('button')).toHaveClass('px-8', 'py-4')
  })

  it('should handle click events', () => {
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click me</Button>)
    
    const button = screen.getByRole('button')
    fireEvent.click(button)
    
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('should be disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled Button</Button>)
    
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveClass('opacity-50')
  })

  it('should show loading state', () => {
    render(<Button loading>Loading Button</Button>)
    
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveClass('opacity-50')
    expect(screen.getByRole('button')).toContainHTML('svg') // Loading spinner
  })

  it('should render with icon on left', () => {
    const icon = <span data-testid="icon">🚀</span>
    render(<Button icon={icon} iconPosition="left">With Icon</Button>)
    
    const button = screen.getByRole('button')
    const iconElement = screen.getByTestId('icon')
    
    expect(button).toContainElement(iconElement)
    // The icon is wrapped in a span with the margin classes
    const iconWrapper = iconElement.parentElement
    expect(iconWrapper).toHaveClass('mr-2')
  })

  it('should render with icon on right', () => {
    const icon = <span data-testid="icon">🚀</span>
    render(<Button icon={icon} iconPosition="right">With Icon</Button>)
    
    const button = screen.getByRole('button')
    const iconElement = screen.getByTestId('icon')
    
    expect(button).toContainElement(iconElement)
    // The icon is wrapped in a span with the margin classes
    const iconWrapper = iconElement.parentElement
    expect(iconWrapper).toHaveClass('ml-2')
  })

  it('should apply custom className', () => {
    render(<Button className="custom-class">Custom</Button>)
    
    const button = screen.getByRole('button')
    expect(button).toHaveClass('custom-class')
  })

  it('should render scan-specific variants', () => {
    const { rerender } = render(<Button variant="discovery-scan">Discovery</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-green-600')

    rerender(<Button variant="full-tcp">Full TCP</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-blue-600')

    rerender(<Button variant="iot-scan">IoT</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-purple-600')

    rerender(<Button variant="vuln-scan">Vuln</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-red-600')
  })
})
