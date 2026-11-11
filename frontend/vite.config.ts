/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// VITE_BASE: ruta pública. En GitHub Pages de un repo es '/<repo>/'; en local, '/'.
// En dev, /api se manda al backend local (uvicorn en :8000), así no hay CORS ni URLs absolutas.
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  // aladin-lite (~2.6 MB, wasm embebido) va en su propio archivo y se carga tarde
  build: { chunkSizeWarningLimit: 3000 },
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000', changeOrigin: true } },
    fs: { allow: ['..'] }, // los fixtures se importan desde ../contracts/fixtures
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
