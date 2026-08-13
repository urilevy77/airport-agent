import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // In dev the React app runs on 5173 and the API on 5001; in production
  // FastAPI serves this build, so these paths are same-origin either way.
  server: { proxy: { '/chat': 'http://localhost:5001', '/health': 'http://localhost:5001' } },
  build: { outDir: 'dist' },
  test: { environment: 'jsdom', globals: true, setupFiles: './src/setupTests.js' },
})
