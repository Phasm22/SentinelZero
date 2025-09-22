import React from 'react'

const Button = ({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  disabled = false, 
  loading = false,
  onClick, 
  className = '',
  type = 'button',
  icon = null,
  iconPosition = 'left',
  fullWidth = false,
  ...props 
}) => {
  // Professional base classes with modern design
  const baseClasses = `
    inline-flex items-center justify-center font-medium rounded-lg 
    transition-all duration-200 ease-in-out
    focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900
    disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:hover:scale-100
    active:scale-95 hover:scale-105
    group relative overflow-hidden
    ${fullWidth ? 'w-full' : ''}
  `.trim()
  
  const variants = {
    // Primary - Main action buttons
    primary: `
      bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800
      text-white shadow-lg hover:shadow-xl hover:shadow-blue-500/25
      border border-blue-500/20 focus:ring-blue-500
      before:absolute before:inset-0 before:bg-gradient-to-r before:from-white/0 before:via-white/20 before:to-white/0
      before:translate-x-[-100%] hover:before:translate-x-[100%] before:transition-transform before:duration-700
    `,
    
    // Secondary - Secondary actions
    secondary: `
      bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800
      text-white shadow-lg hover:shadow-xl hover:shadow-gray-500/25
      border border-gray-500/20 focus:ring-gray-500
    `,
    
    // Success - Positive actions
    success: `
      bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800
      text-white shadow-lg hover:shadow-xl hover:shadow-green-500/25
      border border-green-500/20 focus:ring-green-500
    `,
    
    // Danger - Destructive actions
    danger: `
      bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800
      text-white shadow-lg hover:shadow-xl hover:shadow-red-500/25
      border border-red-500/20 focus:ring-red-500
    `,
    
    // Warning - Caution actions
    warning: `
      bg-gradient-to-r from-yellow-600 to-yellow-700 hover:from-yellow-700 hover:to-yellow-800
      text-white shadow-lg hover:shadow-xl hover:shadow-yellow-500/25
      border border-yellow-500/20 focus:ring-yellow-500
    `,
    
    // Info - Informational actions
    info: `
      bg-gradient-to-r from-cyan-600 to-cyan-700 hover:from-cyan-700 hover:to-cyan-800
      text-white shadow-lg hover:shadow-xl hover:shadow-cyan-500/25
      border border-cyan-500/20 focus:ring-cyan-500
    `,
    
    // Ghost - Subtle actions
    ghost: `
      bg-transparent hover:bg-gray-700/50 text-gray-300 hover:text-white
      border border-gray-600 hover:border-gray-500 backdrop-blur-sm
      focus:ring-gray-500 shadow-sm hover:shadow-md
    `,
    
    // Outline - Outlined actions
    outline: `
      bg-transparent hover:bg-blue-600/10 text-blue-400 hover:text-blue-300
      border border-blue-500 hover:border-blue-400 focus:ring-blue-500
      shadow-sm hover:shadow-md hover:shadow-blue-500/25
    `,
    
    // Error - Error state (for consistency with existing code)
    error: `
      bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800
      text-white shadow-lg hover:shadow-xl hover:shadow-red-500/25
      border border-red-500/20 focus:ring-red-500
    `,
    
    // Scan type variants for consistency
    'discovery-scan': `
      bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800
      text-white shadow-lg hover:shadow-xl hover:shadow-green-500/25
      border border-green-500/20 focus:ring-green-500
    `,
    'full-tcp': `
      bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800
      text-white shadow-lg hover:shadow-xl hover:shadow-blue-500/25
      border border-blue-500/20 focus:ring-blue-500
    `,
    'iot-scan': `
      bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800
      text-white shadow-lg hover:shadow-xl hover:shadow-purple-500/25
      border border-purple-500/20 focus:ring-purple-500
    `,
    'vuln-scan': `
      bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800
      text-white shadow-lg hover:shadow-xl hover:shadow-red-500/25
      border border-red-500/20 focus:ring-red-500
    `
  }
  
  const sizes = {
    xs: 'px-2 py-1 text-xs font-medium',
    sm: 'px-3 py-1.5 text-sm font-medium',
    md: 'px-4 py-2 text-sm font-medium',
    lg: 'px-6 py-3 text-base font-semibold',
    xl: 'px-8 py-4 text-lg font-bold'
  }
  
  const iconClasses = icon ? (iconPosition === 'left' ? 'mr-2' : 'ml-2') : ''
  
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${className}`}
      data-testid={props['data-testid'] || 'button'}
      {...props}
    >
      {loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" data-testid="loading-spinner">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      )}
      {!loading && icon && iconPosition === 'left' && (
        <span className={`${iconClasses} transition-transform group-hover:scale-110`} data-testid="left-icon">
          {icon}
        </span>
      )}
      <span data-testid="button-text">{children}</span>
      {!loading && icon && iconPosition === 'right' && (
        <span className={`${iconClasses} transition-transform group-hover:scale-110`} data-testid="right-icon">
          {icon}
        </span>
      )}
    </button>
  )
}

export default Button 