import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api/apply': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '/api/resume/tailor': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/resume/refine': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/resume/recompile': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/resume/templates': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/resume/download': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/resume/info': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/resume/preview': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/api/chat': {
        target: 'http://localhost:8005',
        changeOrigin: true,
      },
      '/api/v1/dispatch': {
        target: 'http://localhost:8005',
        changeOrigin: true,
      },
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
