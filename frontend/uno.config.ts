import { defineConfig, presetAttributify, presetUno } from 'unocss'

export default defineConfig({
  presets: [presetUno(), presetAttributify()],
  theme: {
    colors: {
      glass: 'var(--cc-content)', text1: 'var(--cc-text-1)',
      text2: 'var(--cc-text-2)', text3: 'var(--cc-text-3)',
      theme: 'var(--cc-theme)', border: 'var(--cc-border)',
    },
  },
})
