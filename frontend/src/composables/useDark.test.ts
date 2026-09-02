// I4:挂载顺序是子先于父 —— DisplayView.onMounted(forceDark) 先跑,
// App.onMounted(initTheme) 后跑。修复前 initTheme 会把显示端打回浅色。
// forced 是模块级状态,每个用例用 resetModules 取全新模块,互不渗漏。
//
// localStorage 用内存桩:本仓 Node ≥22.4 上 globalThis.localStorage 被
// Node 实验性 webstorage 占位(未开 flag 时为 undefined,遮蔽 jsdom 实现),
// 裸 localStorage 不可用;桩在两代 Node 上行为一致。matchMedia jsdom 本就无。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

  it('默认浅色:无保存值时忽略系统深色偏好(Task-20)', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true })) // 系统是深色也不跟随
    const { initTheme } = await freshDark()
    initTheme()
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('cc_theme')).toBeNull() // 默认不落盘,手动选择才持久化
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
