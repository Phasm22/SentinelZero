import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.js'],
    exclude: ['**/node_modules/**', '**/e2e/**'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      thresholds: {
        lines: 25,
        functions: 20,
        statements: 25,
        branches: 15,
      },
      exclude: [
        'node_modules/',
        'src/tests/',
        '**/*.test.js',
        '**/*.test.jsx',
        '**/*.spec.js',
        '**/*.spec.jsx'
      ]
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
})
