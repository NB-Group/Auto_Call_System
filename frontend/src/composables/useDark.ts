import { ref } from 'vue'

const isDark = ref(false)
const KEY = 'cc_theme'

// persist=false:仅本会话视觉态(显示端 forceDark),不写 localStorage —— 否则会把
// 同一 WebView2 profile 下共存的老师端主题也翻成深色(Task-15 review A)
//
// forced:显示端已强制深色后,initTheme 不得回改。挂载顺序是子先于父:
// DisplayView.onMounted(forceDark) 先跑,App.onMounted(initTheme) 后跑,
// 没有 forced 旗标时显示端会被 App 的 saved/system 主题打回浅色(I4)。
let forced = false

function apply(dark: boolean, persist = true) {
  isDark.value = dark
  document.documentElement.classList.toggle('dark', dark)
  if (persist) localStorage.setItem(KEY, dark ? 'dark' : 'light')
}

export function useDark() {
  function initTheme() {
    if (forced) { apply(true, false); return }
    // 无保存值 → 默认浅色(不跟随系统):学校投影/办公环境,用户明确要白底。
    // 默认不落盘(persist=false)—— 只有手动 toggle 才算显式选择、才持久化。
    const saved = localStorage.getItem(KEY)
    if (saved) apply(saved === 'dark')
    else apply(false, false)
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
  function forceDark() { forced = true; apply(true, false) }
  return { isDark, initTheme, toggleDark, forceDark }
}
