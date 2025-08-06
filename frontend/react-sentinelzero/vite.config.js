import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3173,
    host: '0.0.0.0', // Enable network access
    allowedHosts: ['sentinelzero.prox', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        ws: true,
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('Proxying request to: ', proxyReq.path);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('Received response:', proxyRes.statusCode);
          });
        }
      },
      '/scan': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/clear-scan': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/clear-all-data': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/delete-all-scans': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/ping': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
