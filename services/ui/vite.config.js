import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In production the nginx image proxies /api/* to the RAG API service, so the
// bundle only ever calls same-origin /api. In dev, proxy to a local API.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') },
    },
  },
})
