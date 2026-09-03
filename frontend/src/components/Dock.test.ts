// B1:真机(pywebview GTK / WebKitGTK)上报 TeacherView Dock 的 短语/资料 点不动。
// 本测试在 jsdom 里走「真 App + 真 router」整链:登录态 → #/teacher → 点击 Dock
// 里的「短语」→ 断言路由落到 /snippets 且 SnippetManager 真渲染(资料同理)。
// 若此处绿而真机不动,则 bug 在环境层(hit-testing / 事件派发),修复走防御路线
// (Dock 弃 router-link 改 button + router.push,见 Dock.vue 注释)。
//
// localStorage 用内存桩:Node ≥22.4 的实验性 webstorage 会在未开 flag 时以
// undefined 遮蔽 jsdom 实现(同 useDark.test.ts);matchMedia jsdom 本就无。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, type App as VueApp } from 'vue'

function memStorage(): Storage {
  const m = new Map<string, string>()
  return {
    getItem: k => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: k => void m.delete(k),
    clear: () => m.clear(),
    key: i => [...m.keys()][i] ?? null,
    get length() { return m.size },
  } as Storage
}

const ME = {
  id: 1, username: 'zheng', role: 'teacher',
  display_name: '郑老师', office: '203', default_template: '',
}

const j = (data: unknown) =>
  new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } })

async function waitFor(cond: () => boolean, ms = 3000) {
  const t0 = Date.now()
  while (!cond()) {
    if (Date.now() - t0 > ms) throw new Error(`waitFor 超时(${ms}ms)`)
    await new Promise(r => setTimeout(r, 10))
  }
}

/** Dock(身份栏,header.glass-card)里按文案找导航元素 —— 兼容 a 与 button 实现 */
function dockNav(label: string): HTMLElement {
  const dock = document.querySelector('header.glass-card')
  if (!dock) throw new Error('TeacherView 未渲染出 Dock')
  // Array.from:tsconfig 无 DOM.Iterable,NodeOfTypeList 不可展开
  const els = Array.from(dock.querySelectorAll('a, button')) as HTMLElement[]
  const el = els.find(e => e.textContent?.trim() === label)
  if (!el) throw new Error(`Dock 里没找到「${label}」,现有:${els.map(e => e.textContent)}`)
  return el
}

describe('B1:Dock 短语/资料 导航(真 App + 真 hash router)', () => {
  let app: VueApp | null = null
  let root: HTMLDivElement | null = null

  beforeEach(async () => {
    vi.stubGlobal('localStorage', memStorage())
    vi.stubGlobal('sessionStorage', memStorage())
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false }))
    // api 层全桩:登录态 + me + 今日空 + 短语空,页面不因网络分叉
    vi.stubGlobal('fetch', vi.fn(async (input: any) => {
      const url = typeof input === 'string' ? input : input.url
      if (url.includes('/api/me')) return j(ME)
      if (url.includes('/api/calls/today')) return j({ calls: [] })
      if (url.includes('/api/snippets')) return j([])
      if (url.includes('/api/students/search')) return j([])
      return j({ ok: true })
    }))
    localStorage.setItem('cc_token', 'test-token')
    location.hash = '#/teacher'

    // 每用例取全新模块:router 是模块级单例,vue-router 在最后一个 app 卸载时
    // 会拆掉 history 监听并冻结内部 location,复用旧单例会重放到陈旧路由。
    vi.resetModules()
    const { default: App } = await import('../App.vue')
    const { router } = await import('../router')
    app = createApp(App)
    app.use(router)
    root = document.createElement('div')
    document.body.appendChild(root)
    app.mount(root)
    await router.isReady()
    await waitFor(() => !!document.querySelector('header.glass-card'))
  })

  afterEach(() => {
    app?.unmount()
    root?.remove()
    vi.unstubAllGlobals()
    location.hash = ''
  })

  it('点「短语」→ 路由到 /snippets 且 SnippetManager 渲染', async () => {
    dockNav('短语').click()
    await waitFor(() => location.hash === '#/snippets')
    await waitFor(() => document.body.textContent!.includes('短语管理'))
  })

  it('点「资料」→ 路由到 /profile 且 ProfileView 渲染', async () => {
    dockNav('资料').click()
    await waitFor(() => location.hash === '#/profile')
    await waitFor(() => document.body.textContent!.includes('我的资料'))
  })

  it('B1 自愈:懒路由 chunk 404 → 落 hash + 整页重载,旗标防死循环', async () => {
    // jsdom 的 location.reload 不可 configure,router.ts 暴露 reloadNow 接缝
    const { router, isChunkLoadError, reloadNow } = await import('../router')
    const reload = vi.fn()
    reloadNow.fn = reload
    // 文案识别:三种引擎措辞都认,普通错误不认
    expect(isChunkLoadError(new TypeError('Failed to fetch dynamically imported module: http://x/S-1.js'))).toBe(true)
    expect(isChunkLoadError(new Error('Importing a module script failed.'))).toBe(true)
    expect(isChunkLoadError(new TypeError('error loading dynamically imported module'))).toBe(true)
    expect(isChunkLoadError(new Error('unauthorized'))).toBe(false)
    // 临时路由模拟被新构建删掉的旧 chunk
    router.addRoute({
      path: '/__chunk404',
      component: () => Promise.reject(
        new TypeError('Failed to fetch dynamically imported module: http://x/Old-Chunk.js')),
    })
    await expect(router.push('/__chunk404')).rejects.toThrow(/dynamically imported/)
    expect(sessionStorage.getItem('cc_chunk_retry')).toBe('/__chunk404')
    expect(location.hash).toBe('#/__chunk404')
    expect(reload).toHaveBeenCalledTimes(1)
    // 二连失败(旗标已在)不再重载
    await expect(router.push('/__chunk404')).rejects.toThrow(/dynamically imported/)
    expect(reload).toHaveBeenCalledTimes(1)
  })
})
