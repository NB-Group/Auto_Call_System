import { ref } from 'vue'

const isDark = ref(false)
const KEY = 'cc_theme'

function apply(dark: boolean) {
  isDark.value = dark
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem(KEY, dark ? 'dark' : 'light')
}

export function useDark() {
  function initTheme() {
    const saved = localStorage.getItem(KEY)
    apply(saved ? saved === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches)
  }
  function toggleDark() { apply(!isDark.value) }
  return { isDark, initTheme, toggleDark }
}
