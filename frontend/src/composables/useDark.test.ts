// I4:挂载顺序是子先于父 —— DisplayView.onMounted(forceDark) 先跑,
// App.onMounted(initTheme) 后跑。修复前 initTheme 会把显示端打回浅色。
// forced 是模块级状态,每个用例用 resetModules 取全新模块,互不渗漏。
//
// localStorage 用内存桩:本仓 Node ≥22.4 上 globalThis.localStorage 被
// Node 实验性 webstorage 占位(未开 flag 时为 undefined,遮蔽 jsdom 实现),
// 裸 localStorage 不可用;桩在两代 Node 上行为一致。matchMedia jsdom 本就无。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { planReveal } from './useDark'

function memStorage(): Storage {
  const m = new Map<string, string>()
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
    clear: () => m.clear(),
    key: (i) => [...m.keys()][i] ?? null,
    get length() { return m.size },
  } as Storage
}

async function freshDark() {
  vi.resetModules()
  const { useDark } = await import('./useDark')
  return useDark()
}

describe('useDark:forceDark 抵御后至的 initTheme(I4)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memStorage())
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    document.documentElement.classList.remove('dark')
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('未强制:initTheme 跟随已保存的浅色', async () => {
    localStorage.setItem('cc_theme', 'light')
    const { initTheme } = await freshDark()
    initTheme()
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('无保存值:跟随系统深色偏好(Task-21 撤销默认浅色)', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('dark') }))
    const { initTheme } = await freshDark()
    initTheme()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('cc_theme')).toBeNull() // 跟随不落盘,手动选择才持久化
  })

  it('无保存值:系统浅色偏好 → 保持浅色', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    const { initTheme } = await freshDark()
    initTheme()
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('cc_theme')).toBeNull()
  })

  it('有保存值时系统偏好不生效:保存浅色 + 系统深色 → 浅色', async () => {
    localStorage.setItem('cc_theme', 'light')
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    const { initTheme } = await freshDark()
    initTheme()
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('强制后:initTheme 不回改,且不写 localStorage', async () => {
    localStorage.setItem('cc_theme', 'light') // 同 profile 老师端存过浅色
    const { initTheme, forceDark } = await freshDark()
    forceDark() // 子(DisplayView)先挂载
    initTheme() // 父(App)后挂载 —— 修复前此处翻回浅色
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('cc_theme')).toBe('light')
  })
})

describe('B2:主题圆形揭示方向性(GulyGuly 一收一放)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memStorage())
    // reduce 关、系统浅色;需要 reduce 的用例自行覆盖
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false }))
    document.documentElement.classList.remove('dark')
    document.getElementById('cc-vt-base')?.remove()
    document.getElementById('cc-vt-dynamic')?.remove()
    delete (document as any).startViewTransition
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    delete (document as any).startViewTransition
  })

  /** 桩浏览器 View Transition:同步跑回调并交回 ready,聚焦"样式怎么注入" */
  function stubVT() {
    const seen: number[] = []
    ;(document as any).startViewTransition = (cb: () => void) => {
      seen.push(1)
      cb()
      return { ready: Promise.resolve(), finished: Promise.resolve() }
    }
    return seen
  }

  it('planReveal:light→dark 选旧快照收拢,dark→light 选新快照铺开', () => {
    expect(planReveal(false)).toEqual({ toDark: true, animates: 'old' })
    expect(planReveal(true)).toEqual({ toDark: false, animates: 'new' })
  })

  it('light→dark:注入 shrink 关键帧,点击坐标烧成字面量,暗色生效并持久化', async () => {
    const seen = stubVT()
    const { initTheme, toggleDark } = await freshDark()
    initTheme()
    toggleDark({ clientX: 100, clientY: 50 } as MouseEvent)
    const dyn = document.getElementById('cc-vt-dynamic')
    expect(dyn).toBeTruthy()
    expect(seen.length).toBe(1)
    expect(dyn!.textContent).toContain('@keyframes cc-theme-shrink')
    // 终态 0px(收拢),起点 = 对角半径 hypot(max(100,924), max(50,718))
    expect(dyn!.textContent).toContain('circle(0px at 100px 50px)')
    expect(dyn!.textContent).toContain(`circle(${Math.hypot(924, 718)}px at 100px 50px)`)
    // 动画挂在旧快照上,新快照沉底(z-index 1)
    expect(dyn!.textContent).toContain('::view-transition-old(root)')
    expect(dyn!.textContent).toContain('animation: cc-theme-shrink')
    expect(dyn!.textContent).toContain('::view-transition-new(root) { z-index: 1; }')
    // 基线样式注入且只此一份
    expect(document.querySelectorAll('#cc-vt-base').length).toBe(1)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('cc_theme')).toBe('dark')
  })

  it('dark→light:注入 expand 关键帧(新快照铺开),反复切换基线不重复、动态只留一份', async () => {
    stubVT()
    localStorage.setItem('cc_theme', 'dark')
    const { initTheme, toggleDark } = await freshDark()
    initTheme()
    toggleDark() // 无点击点 → 视口中心(jsdom 1024×768:512,384;半径 hypot(512,384)=640)
    const dyn = document.getElementById('cc-vt-dynamic')
    expect(dyn!.textContent).toContain('@keyframes cc-theme-expand')
    expect(dyn!.textContent).toContain('circle(0px at 512px 384px)')
    expect(dyn!.textContent).toContain('circle(640px at 512px 384px)')
    expect(dyn!.textContent).toContain('::view-transition-new(root)')
    expect(dyn!.textContent).toContain('animation: cc-theme-expand')
    expect(dyn!.textContent).toContain('::view-transition-old(root) { z-index: 1; }')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('cc_theme')).toBe('light')
    // 再切一轮:动态样式按新方向重生成(仍 1 份),基线仍只有 1 份
    toggleDark()
    expect(document.querySelectorAll('#cc-vt-dynamic').length).toBe(1)
    expect(document.querySelectorAll('#cc-vt-base').length).toBe(1)
    expect(document.getElementById('cc-vt-dynamic')!.textContent).toContain('cc-theme-shrink')
  })

  it('reduced-motion:跳过 View Transition 直接换主题,不注入任何样式', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce') }))
    const { initTheme, toggleDark } = await freshDark()
    initTheme()
    toggleDark()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.getElementById('cc-vt-dynamic')).toBeNull()
    expect(document.getElementById('cc-vt-base')).toBeNull()
    expect(localStorage.getItem('cc_theme')).toBe('dark') // 切换仍持久化
  })

  it('无 startViewTransition API(旧 WebView):同 reduced-motion 退化路径', async () => {
    const { initTheme, toggleDark } = await freshDark()
    initTheme()
    toggleDark()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.getElementById('cc-vt-dynamic')).toBeNull()
  })
})
