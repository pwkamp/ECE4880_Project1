import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backendProxyTarget =
  process.env.BACKEND_PROXY_TARGET ?? 'http://127.0.0.1:8000'
const frontendServerProxyTarget =
  process.env.FRONTEND_SERVER_PROXY_TARGET ?? 'http://127.0.0.1:8787'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.FRONTEND_HOST ?? '127.0.0.1',
    proxy: {
      // FastAPI BLE connector (backend/main.py). More specific than /api.
      '/api/v1': backendProxyTarget,
      '/api': frontendServerProxyTarget,
    },
  },
})
