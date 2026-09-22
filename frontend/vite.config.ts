import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolveAppConfig } from './src/config/app'

export default defineConfig(({ mode }) => {
  /**
   * Build-time config validation.
   *
   * 这里只验证：
   *
   * - VITE_VTUBER_MODE 是否合法
   * - single 模式是否提供 VITE_DEFAULT_VTUBER_ID
   *
   * 默认 VTuber 是否真的存在，
   * 应该由运行时 GET /vtubers catalog 验证。
   *
   * Vite config 不应该依赖 Pinia Store /
   * runtime API。
   */
  resolveAppConfig(
    loadEnv(
      mode,
      process.cwd(),
      '',
    ),
  )

  return {
    plugins: [
      vue(),
    ],

    resolve: {
      alias: {
        '@': fileURLToPath(
          new URL(
            './src',
            import.meta.url,
          ),
        ),
      },
    },

    server: {
      host: '127.0.0.1',
      port: 5173,

      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,

          rewrite: (
            path,
          ) =>
            path.replace(
              /^\/api/,
              '',
            ),
        },
      },
    },

    build: {
      // ECharts is isolated behind
      // the lazy Timeline route.
      chunkSizeWarningLimit: 550,
    },
  }
})