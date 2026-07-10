import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return

          if (id.includes('/node_modules/vue/') || id.includes('/node_modules/vue-router/') || id.includes('/node_modules/pinia/')) {
            return 'vendor-vue'
          }
          if (id.includes('/node_modules/ant-design-vue/')) {
            return 'vendor-antd'
          }
          if (id.includes('/node_modules/@ant-design/icons-vue/')) {
            return 'vendor-icons'
          }
          if (id.includes('/node_modules/echarts/') || id.includes('/node_modules/vue-echarts/')) {
            return 'vendor-charts'
          }
          if (id.includes('/node_modules/xlsx/')) {
            return 'vendor-xlsx'
          }

          return 'vendor'
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',  // 监听所有网络接口，允许WSL外部访问
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 10000,
        proxyTimeout: 10000,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 10000,
        proxyTimeout: 10000,
      },
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
      },
    },
  },
})