import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        ws: true,
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
