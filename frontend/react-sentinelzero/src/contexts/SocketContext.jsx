import React, { createContext, useContext, useEffect, useState } from 'react'
import { io } from 'socket.io-client'

const SocketContext = createContext()

export const useSocket = () => {
  const context = useContext(SocketContext)
  if (context === undefined) {
    throw new Error('useSocket must be used within a SocketProvider')
  }
  return context
}

export const SocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isInitialized, setIsInitialized] = useState(false)

  useEffect(() => {
    console.log('Initializing Socket.IO client...');
    
    // In development mode (Vite), use the current origin which will be proxied
    // In production, connect directly to the backend
    const isDevelopment = window.location.port === '3173' || window.location.port === '3174';
    const backendUrl = isDevelopment 
      ? window.location.origin  // Use current origin, Vite will proxy /socket.io
      : `http://${window.location.hostname}:5000`;  // Direct connection in production
    
    console.log('🔌 Connecting to backend at:', backendUrl, '(development mode:', isDevelopment, ')');
    
    const newSocket = io(backendUrl, {
      path: '/socket.io',
      transports: ['polling', 'websocket'], // Try polling first, then websocket
      autoConnect: true,
      forceNew: true,
      timeout: 20000, // Increase timeout to 20 seconds
      reconnection: true,
      reconnectionDelay: 1000, // Reduce initial delay
      reconnectionDelayMax: 5000, // Reduce max delay
      reconnectionAttempts: 10, // Increase attempts
      maxHttpBufferSize: 1e8, // 100MB buffer for large scan results
    });

    newSocket.on('connect', () => {
      console.log('🔌 Socket connected to', backendUrl);
      setIsConnected(true);
      setIsInitialized(true);
    });

    newSocket.on('disconnect', (reason) => {
      console.log('🔌 Socket disconnected:', reason);
      setIsConnected(false);
    });

    newSocket.on('connect_error', (error) => {
      console.error('🔌 Socket connection error:', error.message || error);
      console.log('🔌 Ensure backend server is running on', backendUrl);
      
      // Check for common issues
      if (error.message && error.message.includes('timeout')) {
        console.log('💡 This might be caused by multiple backend processes. Try:');
        console.log('   1. Kill all Python processes: pkill -f python');
        console.log('   2. Restart with: cd backend && uv run python app.py');
      }
      
      setIsConnected(false);
      setIsInitialized(true); // Still mark as initialized even if connection fails
    });

    newSocket.on('reconnect', (attemptNumber) => {
      console.log('🔌 Socket reconnected after', attemptNumber, 'attempts');
      setIsConnected(true);
    });

    newSocket.on('reconnect_attempt', (attemptNumber) => {
      console.log('🔌 Socket reconnection attempt:', attemptNumber);
    });

    newSocket.on('reconnect_error', (error) => {
      console.error('🔌 Socket reconnection error:', error.message || error);
    });

    newSocket.on('reconnect_failed', () => {
      console.error('🔌 Socket reconnection failed - all attempts exhausted');
    });

    setSocket(newSocket);

    return () => {
      console.log('🔌 Cleaning up socket connection');
      newSocket.close();
    };
  }, []);

  const value = {
    socket,
    isConnected,
    isInitialized,
  }

  return (
    <SocketContext.Provider value={value}>
      {children}
    </SocketContext.Provider>
  )
} 