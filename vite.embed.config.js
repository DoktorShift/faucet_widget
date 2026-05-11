import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'

// Embed widget build (vanilla JS, no framework) — output goes to dist/embed/
// Bundled as a self-executing IIFE so it works dropped into any 3rd-party page.
export default defineConfig({
  build: {
    outDir: 'dist/embed',
    emptyOutDir: true,
    sourcemap: true,
    lib: {
      entry: fileURLToPath(new URL('./web/embed/embed.js', import.meta.url)),
      name: 'V4VEmbed',
      formats: ['iife'],
      fileName: () => 'embed.js',
    },
    rollupOptions: {
      output: {
        extend: true,
        inlineDynamicImports: true,
      },
    },
    target: 'es2018',
    minify: 'terser',
    terserOptions: {
      compress: { drop_console: true, drop_debugger: true },
      format: { comments: false },
    },
  },
})
