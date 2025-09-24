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
    // In production (static served), connect directly to the backend
    const isDevelopment = import.meta.env?.DEV === true || import.meta.env?.MODE === 'development';
    const configuredUrl = import.meta.env?.VITE_BACKEND_URL;
    
    let backendUrl;
    if (configuredUrl) {
      if (configuredUrl === '/') {
        // Use same origin when configured as '/'
        backendUrl = window.location.origin;
      } else {
        backendUrl = configuredUrl;
      }
    } else {
      // For server deployment, always use the same origin (frontend server proxies to backend)
      // This ensures we connect to sentinelzero.prox:3173, not localhost:5000
      backendUrl = window.location.origin;
      console.log('🔌 Using same origin (proxy) URL:', backendUrl);
    }
    
    console.log('🔌 Socket.IO Debug Info:');
    console.log('  - isDevelopment:', isDevelopment);
    console.log('  - configuredUrl:', configuredUrl);
    console.log('  - window.location.origin:', window.location.origin);
    console.log('  - window.location.hostname:', window.location.hostname);
    console.log('  - backendUrl:', backendUrl);
    
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
      // Force the client to use the proxy in development
      withCredentials: true,
      // Ensure we're using the correct URL
      upgrade: true,
      rememberUpgrade: false
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