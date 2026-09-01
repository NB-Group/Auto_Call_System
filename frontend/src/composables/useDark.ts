import { ref } from 'vue'

const isDark = ref(false)
const KEY = 'cc_theme'

// persist=false:仅本会话视觉态(显示端 forceDark),不写 localStorage —— 否则会把
// 同一 WebView2 profile 下共存的老师端主题也翻成深色(Task-15 review A)
function apply(dark: boolean, persist = true) {
  isDark.value = dark
  document.documentElement.classList.toggle('dark', dark)
  if (persist) localStorage.setItem(KEY, dark ? 'dark' : 'light')
}

export function useDark() {
  function initTheme() {
    const saved = localStorage.getItem(KEY)
    apply(saved ? saved === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches)
  }
  function toggleDark(ev?: MouseEvent) {
    const toDark = !isDark.value
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => { ready: Promise<void> }
    }
    if (!doc.startViewTransition || reduce) { apply(toDark); return }
    const x = ev?.clientX ?? innerWidth / 2
    const y = ev?.clientY ?? innerHeight / 2
    const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
    const vt = doc.startViewTransition(() => apply(toDark))
    vt.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
        { duration: 550, easing: 'ease-in-out', pseudoElement: '::view-transition-new(root)' },
      )
    }).catch(() => { /* 中断即放弃 */ })
  }
  function forceDark() { apply(true, false) }
  return { isDark, initTheme, toggleDark, forceDark }
}
