import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
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
  const [activeScanId, setActiveScanId] = useState(null)

  useEffect(() => {
    console.log('Initializing Socket.IO client...');
    
    // In development mode (Vite), ALWAYS use the current origin which will be proxied
    // This avoids CORS issues by going through the Vite proxy
    // In production (static served), connect directly to the backend
    const isDevelopment = import.meta.env?.DEV === true || import.meta.env?.MODE === 'development';
    const configuredUrl = import.meta.env?.VITE_BACKEND_URL;
    
    let backendUrl;
    if (isDevelopment) {
      // In development, ALWAYS use the proxy to avoid CORS issues
      // The Vite proxy handles /socket.io requests and forwards them to the backend
      backendUrl = window.location.origin;
      console.log('🔌 Development mode: Using proxy URL:', backendUrl);
    } else if (configuredUrl) {
      // In production, use configured URL or same origin
      if (configuredUrl === '/') {
        backendUrl = window.location.origin;
      } else {
        backendUrl = configuredUrl;
      }
      console.log('🔌 Production mode: Using configured URL:', backendUrl);
    } else {
      // Fallback: use same origin
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
      transports: ['websocket', 'polling'],
      autoConnect: true,
      timeout: 20000,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 10,
      maxHttpBufferSize: 1e8,
      withCredentials: false,
      upgrade: true,
      rememberUpgrade: false
    });

    if (newSocket && newSocket.on) {
      newSocket.on('connect', () => {
        console.log('🔌 Socket connected to', backendUrl);
        setIsConnected(true);
        setIsInitialized(true);
        if (activeScanId) {
          newSocket.emit('scan.subscribe', { scan_id: activeScanId });
        }
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
    }

    setSocket(newSocket);

    return () => {
      console.log('🔌 Cleaning up socket connection');
      if (newSocket && newSocket.close) {
        newSocket.close();
      }
    };
  }, []);

  useEffect(() => {
    if (!socket || !isConnected || !activeScanId) return
    socket.emit('scan.subscribe', { scan_id: activeScanId })

    return () => {
      socket.emit('scan.unsubscribe', { scan_id: activeScanId })
    }
  }, [socket, isConnected, activeScanId])

  const subscribeToScan = useCallback((scanId) => {
    setActiveScanId(scanId)
    if (socket && isConnected && scanId) {
      socket.emit('scan.subscribe', { scan_id: scanId })
    }
  }, [socket, isConnected])

  const unsubscribeFromScan = useCallback((scanId) => {
    const resolvedScanId = scanId ?? activeScanId
    if (socket && isConnected && resolvedScanId) {
      socket.emit('scan.unsubscribe', { scan_id: resolvedScanId })
    }
    if (!scanId || scanId === activeScanId) {
      setActiveScanId(null)
    }
  }, [activeScanId, socket, isConnected])

  const value = {
    socket,
    isConnected,
    isInitialized,
    activeScanId,
    subscribeToScan,
    unsubscribeFromScan,
  }

  return (
    <SocketContext.Provider value={value}>
      {children}
    </SocketContext.Provider>
  )
} 
