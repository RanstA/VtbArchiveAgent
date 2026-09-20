import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolveAppConfig } from './src/config/app'
import { TEMPORARY_MOCK_VTUBERS } from './src/stores/vtuber'

export default defineConfig(({ mode }) => {
  const appConfig = resolveAppConfig(loadEnv(mode, process.cwd(), ''))

  if (
    appConfig.vtuberMode === 'single'
    && !TEMPORARY_MOCK_VTUBERS.some((vtuber) => vtuber.id === appConfig.defaultVtuberId)
  ) {
    throw new Error(
      `[VTuber config] Unknown VITE_DEFAULT_VTUBER_ID "${appConfig.defaultVtuberId}" in the temporary frontend VTuber catalog.`,
    )
  }

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    build: {
      // ECharts is isolated behind the lazy Timeline route.
      chunkSizeWarningLimit: 550,
    },
  }
})
