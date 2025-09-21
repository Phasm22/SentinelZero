export function formatTimestamp(timestamp, use24Hour = false) {
  if (!timestamp) {
    return 'No timestamp available'
  }
  
  try {
    // Handle different timestamp formats
    let date
    if (typeof timestamp === 'string') {
      // Try parsing as ISO string first
      date = new Date(timestamp)
    } else if (timestamp instanceof Date) {
      date = timestamp
    } else {
      // Fallback to current time if invalid
      date = new Date()
    }
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return 'Invalid date'
    }
    
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: !use24Hour
    })
  } catch (error) {
    console.error('Error formatting timestamp:', error)
    return 'Invalid date'
  }
} 