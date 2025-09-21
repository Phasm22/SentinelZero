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
  ...props 
}) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 shadow-lg hover:shadow-xl transform hover:scale-105 active:scale-95'
  
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500 border border-blue-500/20',
    secondary: 'bg-gray-600 hover:bg-gray-700 text-white focus:ring-gray-500 border border-gray-500/20',
    success: 'bg-green-600 hover:bg-green-700 text-white focus:ring-green-500 border border-green-500/20',
    danger: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500 border border-red-500/20',
    warning: 'bg-yellow-600 hover:bg-yellow-700 text-white focus:ring-yellow-500 border border-yellow-500/20',
    ghost: 'bg-transparent hover:bg-gray-700/50 text-gray-300 hover:text-white border border-gray-600 hover:border-gray-500 backdrop-blur-sm',
    outline: 'bg-transparent hover:bg-blue-600/10 text-blue-400 hover:text-blue-300 border border-blue-500 hover:border-blue-400',
    'discovery-scan': 'bg-green-600 hover:bg-green-700 text-white focus:ring-green-500 border border-green-500/20 shadow-green-500/25',
    'full-tcp': 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500 border border-blue-500/20 shadow-blue-500/25',
    'iot-scan': 'bg-purple-600 hover:bg-purple-700 text-white focus:ring-purple-500 border border-purple-500/20 shadow-purple-500/25',
    'vuln-scan': 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500 border border-red-500/20 shadow-red-500/25'
  }
  
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base font-semibold',
    xl: 'px-8 py-4 text-lg font-bold'
  }
  
  const disabledClasses = disabled || loading ? 'opacity-50 cursor-not-allowed transform-none hover:scale-100' : 'cursor-pointer'
  
  const iconClasses = icon ? (iconPosition === 'left' ? 'mr-2' : 'ml-2') : ''
  
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${disabledClasses} ${className}`}
      {...props}
    >
      {loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      )}
      {!loading && icon && iconPosition === 'left' && (
        <span className={`${iconClasses} group-hover:scale-110 transition-transform`}>
          {icon}
        </span>
      )}
      {children}
      {!loading && icon && iconPosition === 'right' && (
        <span className={`${iconClasses} group-hover:scale-110 transition-transform`}>
          {icon}
        </span>
      )}
    </button>
  )
}

export default Button 