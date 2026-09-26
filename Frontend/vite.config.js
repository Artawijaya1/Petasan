import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [
      react(),
      {
        name: 'petasan-backend-url',
        transformIndexHtml(html) {
          return html.replace('__PETASAN_BACKEND_URL__', env.VITE_BACKEND_URL || '')
        },
      },
    ],
    server: {
      proxy: {
        '/ws': {
          target: backendTarget,
          ws: true,
        },
      },
    },
  }
})
