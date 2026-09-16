import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // FastAPI BLE connector (backend/main.py). More specific than /api.
      '/api/v1': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8787',
    },
  },
})
