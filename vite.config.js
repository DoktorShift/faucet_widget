import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Landing page build (Vue 3 + Tailwind) — output goes to dist/landing/
export default defineConfig({
  plugins: [vue()],
  root: 'web',
  base: '/',
  // Files in web/public/ are copied to dist/landing/ verbatim. Good for
  // test pages, favicon, robots.txt, etc. — anything not processed by Vite.
  publicDir: 'public',
  build: {
    outDir: '../dist/landing',
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: true,
    rollupOptions: {
      input: {
        landing: fileURLToPath(new URL('./web/index.html', import.meta.url)),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./web/src', import.meta.url)),
    },
  },
})
