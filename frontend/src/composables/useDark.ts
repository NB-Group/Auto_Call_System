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

// ===== B2:主题圆形揭示改方向性(GulyGuly 同款「一收一放」)=====
// 方向决策是纯函数,单测见 useDark.test.ts:
//   light→dark:旧(亮)快照向点击点「收拢」,露出底下已就位的新(暗)快照;
//   dark→light:新(亮)快照从点击点「放大」铺开,盖住底下的旧(暗)快照。
export interface RevealPlan {
  toDark: boolean
  /** 哪个快照跑 clip 动画:old=收拢(light→dark),new=铺开(dark→light) */
  animates: 'old' | 'new'
}

export function planReveal(isDarkNow: boolean): RevealPlan {
  const toDark = !isDarkNow
  return { toDark, animates: toDark ? 'old' : 'new' }
}

let vtBaseInjected = false
const VT_BASE_ID = 'cc-vt-base'
const VT_DYN_ID = 'cc-vt-dynamic'

// 点击坐标 (x, y) 与揭示半径 (r) 直接烧进 @keyframes 字面量 —— 不走 CSS 自定义
// 属性:view-transition 伪元素在独立盒树,:root 的 --var 继承不可靠,一旦断链
// clip-path 回落到 50%,圆心变成屏幕中心而非点击点(GulyGuly 踩过的坑)。
function ensureViewTransitionStyles(plan: RevealPlan, x: number, y: number, r: number) {
  if (typeof document === 'undefined') return

  document.getElementById(VT_DYN_ID)?.remove() // 每次切换按新坐标重生成

  if (!vtBaseInjected) {
    vtBaseInjected = true
    const base = document.createElement('style')
    base.id = VT_BASE_ID
    // 基线:两个快照默认无动画(下方动态样式让其中一个参战)+ 中和 WebView2
    // 非整数 dpr 时 ::view-transition-group(root) 被加了分数 transform 的
    // 重投影偏移(tokens.css 里已有同款,这里自带一份保证独立可用)。
    base.textContent = `
      ::view-transition-group(root) {
        transform: none !important;
        inset: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
      }
      ::view-transition-old(root), ::view-transition-new(root) {
        animation: none !important;
        mix-blend-mode: normal;
        overflow: clip;
        inset: 0 !important;
        width: 100% !important;
        height: 100% !important;
      }
    `
    document.head.appendChild(base)
  }

  const dyn = document.createElement('style')
  dyn.id = VT_DYN_ID
  if (plan.animates === 'old') {
    // light→dark:旧快照收拢,新(暗)沉底被揭开
    dyn.textContent = `
      @keyframes cc-theme-shrink {
        from { clip-path: circle(${r}px at ${x}px ${y}px); }
        to   { clip-path: circle(0px at ${x}px ${y}px); }
      }
      ::view-transition-old(root) {
        animation: cc-theme-shrink 550ms ease-in-out both !important;
        z-index: 2147483646;
      }
      ::view-transition-new(root) { z-index: 1; }
    `
  }
  else {
    // dark→light:新快照铺开,旧(暗)沉底被覆盖
    dyn.textContent = `
      @keyframes cc-theme-expand {
        from { clip-path: circle(0px at ${x}px ${y}px); }
        to   { clip-path: circle(${r}px at ${x}px ${y}px); }
      }
      ::view-transition-new(root) {
        animation: cc-theme-expand 550ms ease-in-out both !important;
        z-index: 2147483646;
      }
      ::view-transition-old(root) { z-index: 1; }
    `
  }
  document.head.appendChild(dyn)
}

export function useDark() {
  function initTheme() {
    if (forced) { apply(true, false); return }
    // Task-21:无保存值 → 跟随系统 prefers-color-scheme(撤销"默认浅色")。
    // 默认不落盘(persist=false)—— 只有手动 toggle 才算显式选择、才持久化。
    const saved = localStorage.getItem(KEY)
    if (saved) apply(saved === 'dark')
    else apply(matchMedia('(prefers-color-scheme: dark)').matches, false)
  }
  function toggleDark(ev?: MouseEvent) {
    const plan = planReveal(isDark.value)
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => { ready: Promise<void> }
    }
    if (!doc.startViewTransition || reduce) { apply(plan.toDark); return }
    const x = ev?.clientX ?? innerWidth / 2
    const y = ev?.clientY ?? innerHeight / 2
    const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
    // 样式要在 startViewTransition 前就位:伪元素创建时即取到字面量坐标
    ensureViewTransitionStyles(plan, x, y, r)
    doc.startViewTransition(() => apply(plan.toDark))
  }
  function forceDark() { forced = true; apply(true, false) }
  return { isDark, initTheme, toggleDark, forceDark }
}
