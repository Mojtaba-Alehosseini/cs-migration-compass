import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// BASE_PATH is set by the Pages workflow to "/<repo>/" so the built site works
// from a project page. Locally and on a custom domain it stays "/".
const base = process.env.BASE_PATH ?? '/'

export default defineConfig({
  base,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    target: 'es2022',
    // History series are large; splitting keeps the first paint small so a
    // visitor arriving from a Reddit link sees data before they bounce.
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ['recharts'],
          motion: ['motion'],
          router: ['react-router-dom'],
        },
      },
    },
  },
})
