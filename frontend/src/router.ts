import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: () => import('./views/LoginView.vue') },
    { path: '/teacher', component: () => import('./views/TeacherView.vue') },
    { path: '/snippets', component: () => import('./views/SnippetManager.vue') },
    { path: '/profile', component: () => import('./views/ProfileView.vue') },
    { path: '/display', component: () => import('./views/DisplayView.vue') },
    { path: '/admin', component: () => import('./views/AdminView.vue') },
    { path: '/server', component: () => import('./views/ServerView.vue') },
  ],
})

// ===== B1 自愈:懒路由 chunk 404 → 整页重载 =====
// 根因(live 探针 scripts/diag_b1_dock_click.py 实证):server/static 被新构建
// 覆盖(prepare_frontend.py 先 rmtree 再拷)时,长跑 WebView 里「尚未加载过」
// 的懒路由(短语/资料)动态 import 404,vue-router 静默中止导航 —— 真机表现
// 即"按钮点不动",且只坏这两个入口。index.html 是 no-store,整页重载必拿到
// 新 chunk 名;sessionStorage 旗标保证同一路径只自愈一次,防重载死循环。
const RETRY_KEY = 'cc_chunk_retry'

/** chunk 加载失败的报文案匹配(Chromium / WebKit / 老 WebKit 三种措辞) */
export function isChunkLoadError(err: unknown): boolean {
  const msg = String((err as Error | undefined)?.message ?? err ?? '')
  return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i.test(msg)
}

// 重载入口做成可替换对象:jsdom 的 location.reload 不可 configure、无法 spy,
// 测试里换 reloadNow.fn 即可断言"确实触发了整页重载"。
export const reloadNow: { fn: () => void } = { fn: () => location.reload() }

router.onError((err, to) => {
  if (!isChunkLoadError(err)) return
  try {
    if (sessionStorage.getItem(RETRY_KEY) === to.fullPath) return // 已自愈过:放弃
    sessionStorage.setItem(RETRY_KEY, to.fullPath)
  } catch { /* sessionStorage 不可用:直接重载一次 */ }
  location.hash = to.fullPath // 先落 hash,重载后直达目标路由
  reloadNow.fn()
})

// 任一成功导航都清旗标:下次再遇 404 仍可自愈一次
router.afterEach(() => {
  try { sessionStorage.removeItem(RETRY_KEY) } catch { /* 同上 */ }
})
