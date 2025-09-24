import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const backendTarget = process.env.VITE_BACKEND_URL || 'http://172.16.0.198:5000'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3173,
    host: '0.0.0.0',
    allowedHosts: ['sentinelzero.prox', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/socket.io': {
        target: backendTarget,
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err) => console.log('proxy error', err))
          proxy.on('proxyReq', (proxyReq) => console.log('Proxying request to:', proxyReq.path))
          proxy.on('proxyRes', (proxyRes) => console.log('Received response:', proxyRes.statusCode))
        }
      }
    }
  },
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version || 'dev')
  },
  build: {
    sourcemap: process.env.VITE_SOURCEMAP === 'true',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom', 'socket.io-client']
        }
      }
    },
    chunkSizeWarningLimit: 700
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'socket.io-client']
  }
})
