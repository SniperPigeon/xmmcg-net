import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue({
      template: {
        // Vidstack 播放器为 Web Components，交给浏览器解析而非当作 Vue 组件。
        compilerOptions: { isCustomElement: (tag) => tag.startsWith('media-') },
      },
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        credentials: 'include', // 确保 Cookie 在代理时被正确转发
      },
    },
  },
})
