import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import UnoCSS from 'unocss/vite'

export default defineConfig({
  base: './',
  // brief 原稿缺 UnoCSS 插件,main.ts 的 virtual:uno.css 无法解析、build 必挂,补上
  plugins: [UnoCSS(), vue()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8800',
      '/ws': { target: 'ws://127.0.0.1:8800', ws: true },
    },
  },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: { environment: 'jsdom' },
})
