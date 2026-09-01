# 实施计划 Phase 2:前端(Vue3 + UnoCSS,Bewly 风格)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 三端 UI(登录/老师端命令面板/显示端大屏/管理后台)+ 设计 token 系统 + WS 客户端,对契约开发并用 vitest 覆盖核心状态机;Linux 三进程联调可出声出画面。

**Architecture:** Vue3 SPA(hash 路由,由服务器静态托管);api.ts/ws.ts 是 CONTRACTS 的唯一前端绑定层;palette.ts 是纯 reducer(选生→拼装→发送),vitest 直测;视觉 token 全部走 `tokens.css` CSS 变量。

**Tech Stack:** Vite 5、Vue 3.4+、TypeScript、UnoCSS(presetUno + presetAttributify)、vitest。

**前置:** Phase 1 完成(`docs/CONTRACTS.md` v1 已冻结,server 可跑)。

## Global Constraints(继承 Phase 1 全部)

- 包管理器 pnpm(node 20);目录 `frontend/`,构建产物 `frontend/dist/`
- 接口只经 `src/api.ts`/`src/ws.ts` 调用,组件不得直接 fetch
- 颜色/圆角/阴影/动效只用 `src/styles/tokens.css` 的 `--cc-*` 变量或其工具类,禁止写死色值
- pywebview bridge 一律防御式:`window.pywebview?.api?.speak?.(text)`
- 显示端强制深色;老师/管理端明暗跟随系统 + 手动切换
- 每 commit:`pnpm --dir frontend build` 绿 + `vitest run` 绿

---

### Task 11: 契约 v1.1 + server 短语搜索 + 前端脚手架与 token 系统

**Files:**
- Modify: `docs/CONTRACTS.md`(v1.1 增补)、`docs/schemas.json`(无新 schema,可不动)
- Modify: `server/api.py`、`server/search.py`
- Test: `tests/test_snippet_search.py`
- Create: `frontend/package.json`、`frontend/vite.config.ts`、`frontend/tsconfig.json`、`frontend/uno.config.ts`、`frontend/index.html`、`frontend/src/main.ts`、`frontend/src/App.vue`、`frontend/src/router.ts`、`frontend/src/styles/tokens.css`、`frontend/src/views/Placeholder*.vue`

**Interfaces:**
- Consumes: CONTRACTS v1
- Produces: `GET /api/snippets/search?q=&limit=6`;前端骨架(`createApp` + hash 路由 `/login /teacher /display /admin /server`);`--cc-*` token 全集

- [ ] **Step 1: 契约 v1.1 增补(CONTRACTS.md 追加)**

```
## v1.1 增补(2026-09-01)
GET /api/snippets/search?q=&limit=6(教师)
匹配:短语拼音首字母前缀 > 短语文本子串;→ [{"id","text","use_count"}](use_count 降序)
```

- [ ] **Step 2: server 侧失败测试 `tests/test_snippet_search.py`**

```python
import pytest

from server.db import connect, init_db
from server.search import search_snippets


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "call.db")
    init_db(conn)
    conn.executemany(
        "INSERT INTO snippets(teacher_id,text,use_count) VALUES (1,?,?)",
        [("订正数学作业", 3), ("订正英语作文", 1), ("带上作图工具", 5),
         ("带上练习册", 2), ("面谈", 0)])
    conn.commit()
    yield conn
    conn.close()


def test_initials_prefix_sorted_by_usage(db):
    rows = search_snippets(db, 1, "dz")
    assert [r["text"] for r in rows] == ["订正数学作业", "订正英语作文"]


def test_substring_fallback(db):
    assert search_snippets(db, 1, "练习")[0]["text"] == "带上练习册"


def test_no_match(db):
    assert search_snippets(db, 1, "zz") == []
```

- [ ] **Step 3: 跑测试确认失败**

Run: `pytest tests/test_snippet_search.py -v`
Expected: FAIL `ImportError: cannot import name 'search_snippets'`

- [ ] **Step 4: 实现(server/search.py 追加 + api.py 挂路由)**

`server/search.py` 追加:
```python
def search_snippets(conn, teacher_id: int, q: str, limit: int = 6) -> list[dict]:
    """短语搜索:拼音首字母前缀 > 文本子串,同级 use_count 降序(CONTRACTS v1.1)。"""
    ql = q.strip().lower()
    if not ql:
        rows = conn.execute(
            "SELECT id,text,use_count FROM snippets WHERE teacher_id=? "
            "ORDER BY use_count DESC LIMIT ?", (teacher_id, limit)).fetchall()
        return [dict(r) for r in rows]
    rows = conn.execute(
        "SELECT id,text,use_count FROM snippets WHERE teacher_id=? "
        "ORDER BY use_count DESC", (teacher_id,)).fetchall()
    scored = []
    for r in rows:
        ini = "".join(lazy_pinyin(r["text"], style=Style.FIRST_LETTER))
        if ini.startswith(ql):
            scored.append((0, -r["use_count"], r))
        elif ql in r["text"].lower():
            scored.append((1, -r["use_count"], r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [dict(r) for _, _, r in scored[:limit]]
```

`server/api.py` 的 `setup_business_routes` 追加(`search_snippets` 顶部已随本任务加入 import):
```python
    async def search_snippets_route(request):
        limit = min(int(request.query.get("limit", 6)), 12)
        return web.json_response(search_snippets(
            request.app["db"], request["teacher"]["id"],
            request.query.get("q", ""), limit))

    router.add_get("/api/snippets/search", search_snippets_route)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/test_snippet_search.py -v` → 3 passed

- [ ] **Step 6: 前端脚手架**

`frontend/package.json`:
```json
{
  "name": "call-center-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0"
  },
  "devDependencies": {
    "@unocss/preset-attributify": "^0.60.0",
    "@unocss/preset-uno": "^0.60.0",
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.4.0",
    "unocss": "^0.60.0",
    "vite": "^5.2.0",
    "vue-tsc": "^2.0.0",
    "vitest": "^1.5.0"
  }
}
```

`frontend/vite.config.ts`:
```ts
import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8800',
      '/ws': { target: 'ws://127.0.0.1:8800', ws: true },
    },
  },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: { environment: 'jsdom' },
})
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler",
    "strict": true, "jsx": "preserve", "esModuleInterop": true,
    "skipLibCheck": true, "noEmit": true, "lib": ["ES2022", "DOM"],
    "types": ["vite/client"],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src/**/*.ts", "src/**/*.vue"]
}
```

`frontend/uno.config.ts`:
```ts
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
```

`frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>叫号中心</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 7: token 系统 `frontend/src/styles/tokens.css`**

```css
/* 设计 token:Bewly 系 DNA(GulyGuly 移植)。只用变量,不写死色值。 */
:root {
  --cc-radius: 12px;
  --cc-radius-half: calc(var(--cc-radius) / 2);
  --cc-top-bar-height: 64px;

  --cc-glass-1: blur(24px) saturate(180%) brightness(1.04);
  --cc-glass-2: blur(36px) saturate(190%) brightness(1.05);

  --cc-shadow-1: 0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.04);
  --cc-shadow-2: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.06);
  --cc-shadow-3: 0 20px 25px -5px rgb(0 0 0 / 0.12), 0 8px 10px -6px rgb(0 0 0 / 0.08);
  --cc-edge-glow: inset 1px 1px 1px -0.5px rgba(255 255 255 / 0.34),
    inset -1px -1px 1px -0.5px rgba(255 255 255 / 0.14),
    inset 0 0 10px rgba(255 255 255 / 0.6);

  --cc-dur-fast: 180ms;
  --cc-dur-cozy: 330ms;
  --cc-dur-slow: 550ms;
  --cc-ease-smooth: cubic-bezier(0.22, 1, 0.36, 1);
  --cc-ease-overshoot: cubic-bezier(0.34, 2, 0.6, 1);

  --cc-theme: hsl(195 100% 42%);
  --cc-theme-10: color-mix(in oklab, var(--cc-theme), transparent 90%);
  --cc-theme-20: color-mix(in oklab, var(--cc-theme), transparent 80%);
  --cc-theme-40: color-mix(in oklab, var(--cc-theme), transparent 60%);
  --cc-theme-80: color-mix(in oklab, var(--cc-theme), transparent 20%);

  --cc-text-1: hsl(217 19% 10%);
  --cc-text-2: hsl(215 19% 22% / 92%);
  --cc-text-3: hsl(215 19% 25% / 82%);
  --cc-text-4: hsl(215 19% 36% / 40%);

  --cc-bg-grad: linear-gradient(180deg, hsl(240 31% 96%) 0%, hsl(0 0% 100%) 100%);
  --cc-content: hsl(0 0% 100% / 0.62);
  --cc-content-solid: hsl(0 0% 100%);
  --cc-fill-1: rgb(131 131 145 / 15%);
  --cc-fill-2: rgb(131 131 145 / 30%);
  --cc-border: rgb(131 131 145 / 18%);
}

:root.dark {
  --cc-shadow-1: 0 4px 6px -1px rgb(0 0 0 / 0.18), 0 2px 4px -2px rgb(0 0 0 / 0.14);
  --cc-shadow-2: 0 10px 15px -3px rgb(0 0 0 / 0.2), 0 4px 6px -4px rgb(0 0 0 / 0.16);
  --cc-shadow-3: 0 20px 25px -5px rgb(0 0 0 / 0.22), 0 8px 10px -6px rgb(0 0 0 / 0.18);
  --cc-edge-glow: inset 1px 1px 1px -0.5px rgba(255 255 255 / 0.18),
    inset -1px -1px 1px -0.5px rgba(255 255 255 / 0.06),
    inset 0 0 10px rgba(255 255 255 / 0.06);

  --cc-text-1: hsl(215 19% 98%);
  --cc-text-2: hsl(215 19% 92% / 92%);
  --cc-text-3: hsl(215 19% 85% / 82%);
  --cc-text-4: hsl(215 19% 74% / 40%);

  --cc-bg-grad: linear-gradient(180deg, hsl(230 12% 8%) 0%, hsl(230 12% 4%) 100%);
  --cc-content: hsl(230 12% 10% / 0.62);
  --cc-content-solid: hsl(230 12% 10%);
  --cc-fill-1: rgb(131 131 145 / 15%);
  --cc-fill-2: rgb(131 131 145 / 30%);
  --cc-border: rgb(131 131 145 / 26%);
}

html, body, #app { height: 100%; margin: 0; }
body {
  font-family: 'Segoe UI', 'MiSans', 'PingFang SC', 'Noto Sans CJK SC',
    'Microsoft YaHei UI', sans-serif;
  color: var(--cc-text-1);
  background: var(--cc-bg-grad);
  background-attachment: fixed;
}

/* 工具类(Uno 管布局,这里管玻璃质感) */
.glass-card {
  background: var(--cc-content);
  backdrop-filter: var(--cc-glass-1);
  -webkit-backdrop-filter: var(--cc-glass-1);
  border: 1px solid var(--cc-border);
  border-radius: var(--cc-radius);
  box-shadow: var(--cc-shadow-1), var(--cc-edge-glow);
}
.glass-pop {
  background: color-mix(in oklab, var(--cc-content-solid), transparent 12%);
  backdrop-filter: var(--cc-glass-2);
  -webkit-backdrop-filter: var(--cc-glass-2);
  border: 1px solid var(--cc-border);
  border-radius: var(--cc-radius);
  box-shadow: var(--cc-shadow-3), var(--cc-edge-glow);
}
.cc-btn {
  border: 1px solid var(--cc-border);
  border-radius: var(--cc-radius-half);
  background: var(--cc-fill-1);
  color: var(--cc-text-1);
  padding: 6px 14px;
  cursor: pointer;
  transition: all var(--cc-dur-fast) var(--cc-ease-smooth);
}
.cc-btn:hover { background: var(--cc-fill-2); transform: translateY(-1px); }
.cc-btn:active { transform: translateY(0) scale(0.97); }
.cc-btn-primary {
  background: var(--cc-theme); color: #fff; border-color: transparent;
  box-shadow: 0 4px 16px var(--cc-theme-40);
}
.cc-input {
  border: 1px solid var(--cc-border);
  border-radius: var(--cc-radius-half);
  background: var(--cc-fill-1);
  color: var(--cc-text-1);
  padding: 8px 12px;
  outline: none;
  transition: border-color var(--cc-dur-fast) var(--cc-ease-smooth),
    box-shadow var(--cc-dur-fast) var(--cc-ease-smooth);
}
.cc-input:focus { border-color: var(--cc-theme); box-shadow: 0 0 0 3px var(--cc-theme-20); }
.cc-chip {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--cc-theme-10); color: var(--cc-theme);
  border: 1px solid var(--cc-theme-20);
  border-radius: 999px; padding: 2px 10px; font-size: 13px;
}

/* 主题切换圆形揭示:中和 WebView2 非整数 dpr 的重投影偏移 */
::view-transition-old(root), ::view-transition-new(root) { animation: none; }
::view-transition-group(root) {
  transform: none !important; inset: 0; width: 100vw; height: 100vh;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --cc-dur-fast: 0ms; --cc-dur-cozy: 0ms; --cc-dur-slow: 0ms;
  }
}
```

- [ ] **Step 8: 入口与路由**

`frontend/src/main.ts`:
```ts
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import 'virtual:uno.css'
import './styles/tokens.css'

createApp(App).use(router).mount('#app')
```

`frontend/src/router.ts`:
```ts
import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: () => import('./views/LoginView.vue') },
    { path: '/teacher', component: () => import('./views/TeacherView.vue') },
    { path: '/display', component: () => import('./views/DisplayView.vue') },
    { path: '/admin', component: () => import('./views/AdminView.vue') },
    { path: '/server', component: () => import('./views/ServerView.vue') },
  ],
})
```

`frontend/src/App.vue`:
```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useDark } from './composables/useDark'

const { initTheme } = useDark()
onMounted(initTheme)
</script>

<template>
  <router-view />
</template>
```

`frontend/src/composables/useDark.ts`(本任务先给最小版,Task 15 补圆形揭示):
```ts
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
```

占位视图(每个 10 行,后续任务替换):`views/LoginView.vue`、`TeacherView.vue`、`DisplayView.vue`、`AdminView.vue`、`ServerView.vue` 均为:
```vue
<template>
  <div style="padding:40px" class="glass-card">LoginView 占位</div>
</template>
```
(文件名对应替换占位文案。)

- [ ] **Step 9: 构建验证**

```bash
corepack enable && cd frontend && pnpm install && pnpm build
```
Expected: `vue-tsc` 0 错误,`vite build` 产出 `dist/`;`pnpm test` 因无测试 "No test files found" 属正常,加 `--passWithNoTests` 到 vitest 调用或暂不跑

- [ ] **Step 10: server 托管验证**

```bash
cp -r frontend/dist server/static   # 临时;Phase 3 由 CI 脚本做
. ../.venv/bin/activate && python -m server &
curl -s http://127.0.0.1:8800/ | head -5
kill %1
```
Expected: 返回 `<!DOCTYPE html>...<div id="app">`

- [ ] **Step 11: Commit**

```bash
git add frontend/ server/ docs/CONTRACTS.md tests/test_snippet_search.py
git commit -m "feat: 前端脚手架+token 系统+契约 v1.1 短语搜索"
```

---

### Task 12: api.ts / ws.ts / palette.ts(纯逻辑层)+ vitest

**Files:**
- Create: `frontend/src/api.ts`、`frontend/src/ws.ts`、`frontend/src/palette.ts`
- Test: `frontend/src/palette.test.ts`

**Interfaces:**
- Consumes: CONTRACTS v1.1(HTTP/WS 全部消息)
- Produces: `api.*`(login/logout/me/updateMe/searchStudents/searchSnippets/call/undo/today/snippets CRUD/admin 全部)、`connectWS({classId,onCall,onRetract,onHello}) -> {close()}`(自动重连+重订阅)、palette 纯 reducer(`reduce(state, event) -> {state, effect}`)

- [ ] **Step 1: 写 `frontend/src/api.ts`**

```ts
// CONTRACTS 的唯一前端 HTTP 绑定层。token 持久化在 localStorage。
const TOKEN_KEY = 'cc_token'

export interface CallItem {
  id: number; student_id: number; class_id: number; teacher_id: number
  message: string; announce: string; created_at: string
  student_name: string; class_name: string; teacher_name: string
  office: string; retracted_at?: string | null
}
export interface StudentHit { id: number; name: string; class_name: string; pinyin_initials: string }
export interface Snippet { id: number; text: string; use_count: number }
export interface MeInfo { id: number; username: string; role: string; display_name: string; office: string; default_template: string }

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token.get() ? { Authorization: `Bearer ${token.get()}` } : {}),
      ...init?.headers,
    },
  })
  if (r.status === 401 && location.hash !== '#/login') {
    token.clear(); location.hash = '#/login'
    throw new Error('unauthorized')
  }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `http ${r.status}`)
  return r.status === 204 ? undefined : r.json()
}

export const api = {
  login: (username: string, password: string) =>
    j<{ token: string; role: string; display_name: string; office: string }>(
      '/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => j<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),
  me: () => j<MeInfo>('/api/me'),
  updateMe: (patch: Partial<Pick<MeInfo, 'display_name' | 'office' | 'default_template'>>) =>
    j<MeInfo>('/api/me', { method: 'PUT', body: JSON.stringify(patch) }),
  bootstrapStatus: () => j<{ needs_admin: boolean; version: string }>('/api/bootstrap/status'),
  bootstrapAdmin: (username: string, password: string, display_name?: string) =>
    j<{ token: string; role: string }>('/api/bootstrap/admin',
      { method: 'POST', body: JSON.stringify({ username, password, display_name }) }),
  classes: () => j<{ id: number; name: string; ord: number }[]>('/api/classes'),
  searchStudents: (q: string, limit = 8) =>
    j<StudentHit[]>(`/api/students/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  searchSnippets: (q: string, limit = 6) =>
    j<Snippet[]>(`/api/snippets/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  call: (student_id: number, snippet_ids: number[], free_text: string) =>
    j<{ call: CallItem }>('/api/calls',
      { method: 'POST', body: JSON.stringify({ student_id, snippet_ids, free_text }) }),
  undo: (id: number) => j<{ ok: boolean }>(`/api/calls/${id}`, { method: 'DELETE' }),
  today: () => j<{ calls: CallItem[] }>('/api/calls/today'),
  snippets: () => j<Snippet[]>('/api/snippets'),
  addSnippet: (text: string) => j<{ ok: boolean }>('/api/snippets',
    { method: 'POST', body: JSON.stringify({ text }) }),
  delSnippet: (id: number) => j<{ ok: boolean }>(`/api/snippets/${id}`, { method: 'DELETE' }),
  admin: {
    teachers: () => j<any[]>('/api/admin/teachers'),
    addTeacher: (t: any) => j<{ id: number }>('/api/admin/teachers',
      { method: 'POST', body: JSON.stringify(t) }),
    updateTeacher: (id: number, patch: any) => j<{ ok: boolean }>(`/api/admin/teachers/${id}`,
      { method: 'PUT', body: JSON.stringify(patch) }),
    delTeacher: (id: number) => j<{ ok: boolean }>(`/api/admin/teachers/${id}`, { method: 'DELETE' }),
    addClass: (name: string, ord = 0) => j<{ id: number; name: string; ord: number }>(
      '/api/admin/classes', { method: 'POST', body: JSON.stringify({ name, ord }) }),
    delClass: (id: number) => j<{ ok: boolean }>(`/api/admin/classes/${id}`, { method: 'DELETE' }),
    importStudents: (classId: number, text: string) =>
      j<{ imported: number; skipped: string[] }>(`/api/admin/classes/${classId}/students`,
        { method: 'POST', body: JSON.stringify({ text }) }),
    history: (date?: string) => j<{ calls: CallItem[] }>(
      `/api/admin/calls${date ? `?date=${date}` : ''}`),
    serverInfo: () => j<{ version: string; displays: number }>('/api/server/info'),
  },
}
```

- [ ] **Step 2: 写 `frontend/src/ws.ts`**

```ts
// 显示端 WS:自动重连(指数退避,上限 10s)+ 重连后自动重订阅。
import type { CallItem } from './api'
import { token } from './api'

export interface WSHandlers {
  classId?: number
  onCall?: (call: CallItem) => void
  onRetract?: (callId: number) => void
  onHello?: () => void
  onStatus?: (online: boolean) => void
}

export function connectWS(h: WSHandlers) {
  let closed = false
  let ws: WebSocket | null = null
  let delay = 1000

  function open() {
    const t = token.get()
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws${t ? `?token=${t}` : ''}`
    ws = new WebSocket(url)
    ws.onopen = () => {
      delay = 1000
      if (h.classId !== undefined)
        ws?.send(JSON.stringify({ type: 'subscribe', class_id: h.classId }))
      h.onStatus?.(true)
    }
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'hello') h.onHello?.()
      else if (msg.type === 'call') h.onCall?.(msg.call as CallItem)
      else if (msg.type === 'retract') h.onRetract?.(msg.call_id)
    }
    ws.onclose = () => {
      h.onStatus?.(false)
      if (!closed) setTimeout(open, delay = Math.min(delay * 1.6, 10000))
    }
  }
  open()

  return {
    subscribe(classId: number) {
      h.classId = classId
      if (ws?.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({ type: 'subscribe', class_id: classId }))
    },
    close() { closed = true; ws?.close() },
  }
}
```

- [ ] **Step 3: 写失败测试 `frontend/src/palette.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { initial, reduce } from './palette'

const S = { id: 1, name: '梁皓文', class_name: '高二(3)班', pinyin_initials: 'lhw' }
const SN = { id: 7, text: '订正数学作业', use_count: 3 }

describe('palette 状态机', () => {
  it('选生:回车进入拼装', () => {
    let st = initial
    st = reduce(st, { t: 'type', ch: 'l' }).state
    const { state } = reduce(st, { t: 'enter', students: [S], snippets: [] })
    expect(state.phase).toBe('compose')
    expect(state.student?.name).toBe('梁皓文')
  })

  it('拼装:回车挂短语 chip,空 query 回车发送', () => {
    let st = reduce({ ...initial, phase: 'compose', student: S }, {}) as typeof initial
    st = reduce(st, { t: 'type', ch: 'd' }).state
    st = reduce(st, { t: 'enter', students: [], snippets: [SN] }).state
    expect(st.chips.map(c => c.text)).toEqual(['订正数学作业'])
    expect(st.query).toBe('')
    const { state, effect } = reduce(st, { t: 'enter', students: [], snippets: [SN] })
    expect(effect).toEqual({ kind: 'send', student: S, snippetIds: [7], freeText: '' })
    expect(state.phase).toBe('student')
  })

  it('拼装:无匹配短语时把 query 作为自由文本直接发送', () => {
    const st = { ...initial, phase: 'compose' as const, student: S, query: '记得带圆规' }
    const { effect } = reduce(st, { t: 'enter', students: [], snippets: [] })
    expect(effect).toEqual({ kind: 'send', student: S, snippetIds: [], freeText: '记得带圆规' })
  })

  it('Tab 切自由文本,回车带 freeText 发送', () => {
    let st = { ...initial, phase: 'compose' as const, student: S }
    st = reduce(st, { t: 'tab' }).state
    st = reduce(st, { t: 'type', ch: '带书' }).state
    const { effect } = reduce(st, { t: 'enter', students: [], snippets: [] })
    expect(effect?.kind === 'send' && effect.freeText === '带书').toBe(true)
  })

  it('空 query 退格:先弹 chip,再退回选生', () => {
    let st = { ...initial, phase: 'compose' as const, student: S, chips: [SN] }
    st = reduce(st, { t: 'backspace' }).state
    expect(st.chips).toEqual([])
    st = reduce(st, { t: 'backspace' }).state
    expect(st.phase).toBe('student')
  })

  it('Esc 清空回到选生;sent 重置全部', () => {
    let st = { ...initial, phase: 'compose' as const, student: S, chips: [SN] }
    st = reduce(st, { t: 'esc' }).state
    expect(st.chips).toEqual([])
    st = reduce(st, { t: 'esc' }).state
    expect(st).toEqual(initial)
    const sent = reduce({ ...initial, phase: 'compose' as const, student: S }, { t: 'sent' })
    expect(sent.state).toEqual(initial)
  })

  it('compose 直接回车 = 无附加消息发送(最快路径)', () => {
    const { effect } = reduce({ ...initial, phase: 'compose' as const, student: S },
      { t: 'enter', students: [], snippets: [SN] })
    expect(effect).toEqual({ kind: 'send', student: S, snippetIds: [], freeText: '' })
  })
})
```

- [ ] **Step 4: 跑测试确认失败**

Run: `cd frontend && pnpm vitest run src/palette.test.ts`
Expected: FAIL `Failed to resolve import "./palette"`

- [ ] **Step 5: 实现 `frontend/src/palette.ts`**

```ts
// 老师端命令面板纯状态机:选生 → 拼装(chip/自由文本) → 发送。
import type { Snippet, StudentHit } from './api'

export interface PaletteState {
  phase: 'student' | 'compose'
  query: string
  student: StudentHit | null
  chips: Snippet[]
  freeText: boolean
  activeIndex: number
}

export type SendEffect = {
  kind: 'send'
  student: StudentHit
  snippetIds: number[]
  freeText: string
}

export type PaletteEvent =
  | { t: 'type'; ch: string }
  | { t: 'backspace' }
  | { t: 'up' }
  | { t: 'down' }
  | { t: 'enter'; students: StudentHit[]; snippets: Snippet[] }
  | { t: 'tab' }
  | { t: 'esc' }
  | { t: 'sent' }

export const initial: PaletteState = {
  phase: 'student', query: '', student: null, chips: [],
  freeText: false, activeIndex: 0,
}

export function reduce(
  s: PaletteState,
  e: PaletteEvent,
): { state: PaletteState; effect: SendEffect | null } {
  switch (e.t) {
    case 'type':
      return { state: { ...s, query: s.query + e.ch, activeIndex: 0 }, effect: null }
    case 'backspace':
      if (s.query) return { state: { ...s, query: s.query.slice(0, -1) }, effect: null }
      if (s.phase === 'compose') {
        if (s.chips.length)
          return { state: { ...s, chips: s.chips.slice(0, -1) }, effect: null }
        return { state: { ...initial }, effect: null }
      }
      return { state: s, effect: null }
    case 'up':
      return { state: { ...s, activeIndex: Math.max(0, s.activeIndex - 1) }, effect: null }
    case 'down':
      return { state: { ...s, activeIndex: s.activeIndex + 1 }, effect: null }
    case 'enter':
      return onEnter(s, e)
    case 'tab':
      if (s.phase === 'compose')
        return { state: { ...s, freeText: !s.freeText, query: '', activeIndex: 0 }, effect: null }
      return { state: s, effect: null }
    case 'esc':
      if (s.phase === 'compose' && s.chips.length)
        return { state: { ...s, chips: [] }, effect: null }
      return { state: { ...initial }, effect: null }
    case 'sent':
      return { state: { ...initial }, effect: null }
  }
}

function onEnter(
  s: PaletteState,
  e: Extract<PaletteEvent, { t: 'enter' }>,
): { state: PaletteState; effect: SendEffect | null } {
  if (s.phase === 'student') {
    if (!e.students.length) return { state: s, effect: null }
    const student = e.students[Math.min(s.activeIndex, e.students.length - 1)]
    return {
      state: { phase: 'compose', query: '', student, chips: [], freeText: false, activeIndex: 0 },
      effect: null,
    }
  }
  if (!s.student) return { state: initial, effect: null }

  if (s.freeText) {
    return {
      state: { ...initial },
      effect: {
        kind: 'send', student: s.student,
        snippetIds: s.chips.map(c => c.id), freeText: s.query.trim(),
      },
    }
  }
  if (s.query) {
    if (e.snippets.length) {
      const snip = e.snippets[Math.min(s.activeIndex, e.snippets.length - 1)]
      if (s.chips.some(c => c.id === snip.id))
        return { state: { ...s, query: '' }, effect: null }
      return { state: { ...s, chips: [...s.chips, snip], query: '', activeIndex: 0 }, effect: null }
    }
    return {
      state: { ...initial },
      effect: {
        kind: 'send', student: s.student,
        snippetIds: s.chips.map(c => c.id), freeText: s.query.trim(),
      },
    }
  }
  return {
    state: { ...initial },
    effect: {
      kind: 'send', student: s.student,
      snippetIds: s.chips.map(c => c.id), freeText: '',
    },
  }
}
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd frontend && pnpm vitest run`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat: api/ws 绑定层 + palette 状态机(7 测试)"
```

---

### Task 13: 登录页 + 老师端(命令面板 UI)

**Files:**
- Modify: `frontend/src/views/LoginView.vue`(替换占位)
- Modify: `frontend/src/views/TeacherView.vue`(替换占位)
- Create: `frontend/src/components/Palette.vue`、`frontend/src/components/Dock.vue`、`frontend/src/components/Toasts.vue`
- Create: `frontend/src/composables/useToast.ts`

**Interfaces:**
- Consumes: `api`、`reduce/initial`(palette)、`useDark`
- Produces: 老师端完整界面;`useToast().push(msg)`;`Palette.vue` props `{refreshKey}` 无、emit `sent(call)`

- [ ] **Step 1: `useToast` + `Toasts.vue`**

`frontend/src/composables/useToast.ts`:
```ts
import { ref } from 'vue'

const toasts = ref<{ id: number; text: string }[]>([])
let seq = 0

export function useToast() {
  function push(text: string) {
    const id = ++seq
    toasts.value.push({ id, text })
    setTimeout(() => (toasts.value = toasts.value.filter(t => t.id !== id)), 2500)
  }
  return { toasts, push }
}
```

`frontend/src/components/Toasts.vue`:
```vue
<script setup lang="ts">
import { useToast } from '../composables/useToast'
const { toasts } = useToast()
</script>

<template>
  <div fixed bottom-6 left-1/2 translate-x--1/2 flex="~ col gap-2" z-50>
    <TransitionGroup name="toast">
      <div v-for="t in toasts" :key="t.id" class="glass-pop" px-5 py-3 text-14px>
        {{ t.text }}
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active { transition: all var(--cc-dur-cozy) var(--cc-ease-overshoot); }
.toast-leave-active { transition: all var(--cc-dur-fast) ease; }
.toast-enter-from { opacity: 0; transform: translateY(16px) scale(0.95); }
.toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
```

- [ ] **Step 2: `LoginView.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, token } from '../api'

const router = useRouter()
const username = ref('')
const password = ref('')
const err = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true; err.value = ''
  try {
    const r = await api.login(username.value.trim(), password.value)
    token.set(r.token)
    router.replace(r.role === 'admin' ? '/admin' : '/teacher')
  } catch (e: any) {
    err.value = e.message === 'unauthorized' ? '用户名或密码错误' : e.message
  } finally { busy.value = false }
}
</script>

<template>
  <div h-full flex="~ items-center justify-center">
    <form class="glass-card" w-360px p-8 flex="~ col gap-4" @submit.prevent="submit">
      <h1 text-22px font-600 m-0>叫号中心</h1>
      <p text-13px m-0 style="color: var(--cc-text-3)">老师登录</p>
      <input v-model="username" class="cc-input" placeholder="用户名" autocomplete="username">
      <input v-model="password" class="cc-input" type="password" placeholder="密码"
             autocomplete="current-password">
      <div v-if="err" text-13px style="color: var(--cc-theme)">{{ err }}</div>
      <button class="cc-btn cc-btn-primary" :disabled="busy" mt-2>
        {{ busy ? '登录中…' : '登 录' }}
      </button>
    </form>
  </div>
</template>
```

- [ ] **Step 3: `Dock.vue`(顶栏)**

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { api, token } from '../api'
import { useDark } from '../composables/useDark'

defineProps<{ name: string; office: string }>()
const router = useRouter()
const { isDark, toggleDark } = useDark()

async function logout() {
  try { await api.logout() } catch { /* 忽略 */ }
  token.clear()
  router.replace('/login')
}
</script>

<template>
  <header class="glass-card" flex="~ items-center gap-3" h-64px px-6 mb-6>
    <div flex-1 flex="~ items-center gap-2" text-15px>
      <span style="color: var(--cc-theme)">●</span>
      <b>叫号中心</b>
      <span text-13px style="color: var(--cc-text-3)">{{ name }} · {{ office }}</span>
    </div>
    <button class="cc-btn" title="切换主题" @click="toggleDark($event)">
      {{ isDark ? '☀️' : '🌙' }}
    </button>
    <button class="cc-btn" @click="logout">退出</button>
  </header>
</template>
```

- [ ] **Step 4: `Palette.vue`(核心组件)**

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type CallItem, type Snippet, type StudentHit } from '../api'
import { initial, reduce, type PaletteState, type SendEffect } from '../palette'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ sent: [call: CallItem] }>()
const { push } = useToast()

const state = ref<PaletteState>({ ...initial })
const students = ref<StudentHit[]>([])
const snippets = ref<Snippet[]>([])
const inputEl = ref<HTMLInputElement | null>(null)
const listEl = ref<HTMLElement | null>(null)

const results = computed(() =>
  state.value.phase === 'student'
    ? students.value.map(s => ({ key: s.id, title: s.name, sub: s.class_name }))
    : snippets.value.map(s => ({ key: s.id, title: s.text, sub: `×${s.use_count}` })))

let searchSeq = 0
watch(() => [state.value.phase, state.value.query] as const, async ([phase, q]) => {
  if (phase === 'compose' && state.value.freeText) { students.value = []; snippets.value = []; return }
  const seq = ++searchSeq
  if (!q.trim()) {
    if (phase === 'student') students.value = []
    else snippets.value = await api.searchSnippets('')
    return
  }
  const res = phase === 'student'
    ? await api.searchStudents(q).catch(() => [])
    : await api.searchSnippets(q).catch(() => [])
  if (seq === searchSeq) {
    if (phase === 'student') students.value = res as StudentHit[]
    else snippets.value = res as Snippet[]
  }
})

function dispatch(e: Parameters<typeof reduce>[1]) {
  const { state: next, effect } = reduce(state.value, e)
  state.value = next
  if (effect) void send(effect)
}
async function send(effect: SendEffect) {
  try {
    const { call } = await api.call(
      effect.student.id, effect.snippetIds, effect.freeText)
    push(`已呼叫 ${effect.student.name} · ${call.class_name}`)
    emit('sent', call)
  } catch (e: any) {
    push(`发送失败:${e.message}`)
    state.value = { ...initial, student: effect.student, phase: 'compose' }
  }
}

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === 'ArrowDown') { dispatch({ t: 'down' }); ev.preventDefault() }
  else if (ev.key === 'ArrowUp') { dispatch({ t: 'up' }); ev.preventDefault() }
  else if (ev.key === 'Enter') {
    dispatch({ t: 'enter', students: students.value, snippets: snippets.value })
    ev.preventDefault()
  }
  else if (ev.key === 'Tab') { dispatch({ t: 'tab' }); ev.preventDefault() }
  else if (ev.key === 'Escape') dispatch({ t: 'esc' })
  else if (ev.key === 'Backspace') dispatch({ t: 'backspace' })
  else if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey) dispatch({ t: 'type', ch: ev.key })
}

watch(() => state.value.activeIndex, () => {
  listEl.value?.querySelector('.active')?.scrollIntoView({ block: 'nearest' })
})
onMounted(() => inputEl.value?.focus())

const PLACEHOLDER = computed(() =>
  state.value.phase === 'student'
    ? '输入姓名或拼音(如 lhw)…'
    : state.value.freeText ? '自由输入附加消息,回车发送…'
    : '选短语(如 dz)回车挂载 · Tab 自由输入 · 直接回车发送')
</script>

<template>
  <div class="glass-card" p-4 pos-relative @mousedown="inputEl?.focus()">
    <!-- 已选学生与 chips -->
    <div v-if="state.phase === 'compose'" flex="~ items-center gap-2 wrap" mb-3 text-15px>
      <span class="cc-chip" font-600 text-15px style="background: var(--cc-theme); color: #fff; border-color: transparent">
        {{ state.student?.name }}
      </span>
      <span v-for="c in state.chips" :key="c.id" class="cc-chip">✚ {{ c.text }}</span>
      <span v-if="state.freeText" text-12px style="color: var(--cc-text-4)">自由输入</span>
    </div>

    <input ref="inputEl" :value="state.query" class="cc-input w-full text-17px"
           :placeholder="PLACEHOLDER" mb-2 autocomplete="off" spellcheck="false"
           @keydown="onKeydown">

    <div ref="listEl" max-h-320px overflow-auto flex="~ col gap-1">
      <div v-for="(r, i) in results" :key="r.key"
           :class="['result', { active: i === Math.min(state.activeIndex, results.length - 1) }]"
           flex="~ items-center justify-between" px-3 py-2 rounded-8px cursor-pointer
           @click="state.activeIndex = i;
                   dispatch({ t: 'enter', students, snippets })">
        <span>{{ r.title }}</span>
        <span text-12px style="color: var(--cc-text-3)">{{ r.sub }}</span>
      </div>
      <div v-if="!results.length && (state.query || state.phase === 'student')"
           px-3 py-2 text-13px style="color: var(--cc-text-4)">
        {{ state.phase === 'student' ? '开始输入以搜索学生' : '无匹配短语 · 回车将作为自由文本发送' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.result.active { background: var(--cc-theme-10); }
.result:hover { background: var(--cc-fill-1); }
input { border: none; background: transparent; padding-left: 4px; }
input:focus { box-shadow: none; border: none; }
</style>
```
(注:组件内 input 覆写了 `.cc-input` 的底色,搜索框与卡片融为一体;`w-full` 来自 Uno。`@click` 里多行表达式太挤的话提为方法 `pick(i)`。)

- [ ] **Step 5: `TeacherView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, token, type CallItem, type MeInfo } from '../api'
import Dock from '../components/Dock.vue'
import Palette from '../components/Palette.vue'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

const me = ref<MeInfo | null>(null)
const today = ref<CallItem[]>([])
const { push } = useToast()
const now = ref(Date.now())
setInterval(() => (now.value = Date.now()), 1000)

async function refresh() { today.value = (await api.today()).calls }
onMounted(async () => {
  if (!token.get()) return location.assign('#/login')
  try { me.value = await api.me() } catch { return }
  await refresh()
})

async function undo(c: CallItem) {
  try { await api.undo(c.id); await refresh(); push(`已撤销 ${c.student_name}`) }
  catch (e: any) { push(`撤销失败:${e.message === 'gone' ? '超过 60 秒' : e.message}`) }
}
const undoable = (c: CallItem) =>
  !c.retracted_at && now.value - new Date(c.created_at.replace(' ', 'T')).getTime() < 60000
</script>

<template>
  <div v-if="me" max-w-880px mx-auto px-6 py-6 min-h-full>
    <Dock :name="me.display_name" :office="me.office" />
    <Palette @sent="refresh" />
    <section mt-6>
      <h2 text-14px font-600 style="color: var(--cc-text-2)">今日已叫({{ today.length }})</h2>
      <div class="glass-card" mt-3 p-2 flex="~ col">
        <div v-for="c in today" :key="c.id" flex="~ items-center gap-3" px-3 py-2>
          <span w-64px text-13px style="color: var(--cc-text-3)">{{ c.created_at.slice(11, 16) }}</span>
          <b>{{ c.student_name }}</b>
          <span text-12px style="color: var(--cc-text-3)">{{ c.class_name }}</span>
          <span v-if="c.message" class="cc-chip">{{ c.message }}</span>
          <span v-if="c.retracted_at" text-12px style="color: var(--cc-text-4)">已撤销</span>
          <span flex-1 />
          <button v-if="undoable(c)" class="cc-btn" text-13px @click="undo(c)">撤销</button>
        </div>
        <div v-if="!today.length" px-3 py-4 text-13px style="color: var(--cc-text-4)">
          还没有叫号记录,从上方搜索开始 ⌘
        </div>
      </div>
    </section>
    <Toasts />
  </div>
</template>
```

- [ ] **Step 6: 三进程手动联调**

```bash
# 终端1(服务器,先建管理员)
TTS=none ../.venv/bin/python -m server
# 终端2(前端 dev)
pnpm --dir frontend dev
# 浏览器 http://127.0.0.1:5173 → 首次经 #/server 建管理员(Phase 2 Task 16 前用 curl):
curl -s -X POST localhost:8800/api/bootstrap/admin -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
# 再建老师+班级+学生(curl /api/admin/*),然后浏览器登录 → 敲 lhw → 回车 → 回车
```
Expected: 今日已叫列表出现记录;`curl localhost:8800/api/calls/today -H "Authorization: Bearer <token>"` 一致

- [ ] **Step 7: 构建与提交**

```bash
cd frontend && pnpm build && cd ..
git add frontend/
git commit -m "feat: 登录页+老师端命令面板(chip 拼装+撤销+toast)"
```

---

### Task 14: 短语管理页 + 老师资料

**Files:**
- Modify: `frontend/src/views/TeacherView.vue`(Dock 下加设置入口)
- Create: `frontend/src/views/SnippetManager.vue`、`frontend/src/views/ProfileView.vue`
- Modify: `frontend/src/router.ts`(加 `/snippets`、`/profile`)

**Interfaces:**
- Consumes: `api.snippets/addSnippet/delSnippet/updateMe`
- Produces: 短语 CRUD 页(增删+使用次数排序);资料页(姓名/办公室/默认模板)

- [ ] **Step 1: 路由追加**

```ts
{ path: '/snippets', component: () => import('./views/SnippetManager.vue') },
{ path: '/profile', component: () => import('./views/ProfileView.vue') },
```

- [ ] **Step 2: `SnippetManager.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type Snippet } from '../api'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

const items = ref<Snippet[]>([])
const text = ref('')
const { push } = useToast()

async function refresh() { items.value = await api.snippets() }
onMounted(refresh)

async function add() {
  if (!text.value.trim()) return
  await api.addSnippet(text.value.trim())
  text.value = ''
  await refresh(); push('已添加')
}
async function del(id: number) {
  await api.delSnippet(id); await refresh(); push('已删除')
}
</script>

<template>
  <div max-w-720px mx-auto px-6 py-6>
    <div flex="~ items-center justify-between" mb-4>
      <h1 text-20px font-600 m-0>短语管理</h1>
      <a href="#/teacher" class="cc-btn" style="text-decoration:none">返回</a>
    </div>
    <div class="glass-card" p-4 mb-4 flex="~ items-center gap-2">
      <input v-model="text" class="cc-input" flex-1 placeholder="新短语,如:订正数学作业"
             @keydown.enter="add">
      <button class="cc-btn cc-btn-primary" @click="add">添加</button>
    </div>
    <div class="glass-card" p-2 flex="~ col">
      <div v-for="s in items" :key="s.id" flex="~ items-center gap-3" px-3 py-2>
        <span class="cc-chip">✚ {{ s.text }}</span>
        <span text-12px style="color: var(--cc-text-3)">用了 {{ s.use_count }} 次</span>
        <span flex-1 />
        <button class="cc-btn" text-13px @click="del(s.id)">删除</button>
      </div>
      <div v-if="!items.length" px-3 py-4 text-13px style="color: var(--cc-text-4)">
        还没有短语。添加几条常用的,叫号时敲首字母就能挂上。
      </div>
    </div>
    <Toasts />
  </div>
</template>
```

- [ ] **Step 3: `ProfileView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type MeInfo } from '../api'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

const me = ref<MeInfo | null>(null)
const { push } = useToast()
onMounted(async () => { me.value = await api.me() })

async function save() {
  if (!me.value) return
  me.value = await api.updateMe({
    display_name: me.value.display_name, office: me.value.office,
    default_template: me.value.default_template,
  })
  push('已保存')
}
</script>

<template>
  <div v-if="me" max-w-560px mx-auto px-6 py-6>
    <div flex="~ items-center justify-between" mb-4>
      <h1 text-20px font-600 m-0>我的资料</h1>
      <a href="#/teacher" class="cc-btn" style="text-decoration:none">返回</a>
    </div>
    <form class="glass-card" p-6 flex="~ col gap-4" @submit.prevent="save">
      <label flex="~ col gap-1" text-13px>
        称呼(播报用)
        <input v-model="me.display_name" class="cc-input" placeholder="郑老师">
      </label>
      <label flex="~ col gap-1" text-13px>
        办公室位置
        <input v-model="me.office" class="cc-input" placeholder="203办公室">
      </label>
      <label flex="~ col gap-1" text-13px>
        播报模板(可用 {student} {teacher} {office})
        <input v-model="me.default_template" class="cc-input">
      </label>
      <div text-12px style="color: var(--cc-text-3)">
        预览:请梁皓文同学到{{ me.display_name || '…' }}{{ me.office || '…' }}
      </div>
      <button class="cc-btn cc-btn-primary" type="submit">保存</button>
    </form>
    <Toasts />
  </div>
</template>
```

- [ ] **Step 4: TeacherView 的 Dock 增加入口(模板里加两行链接)**

```html
<router-link to="/snippets" class="cc-btn" style="text-decoration:none">短语</router-link>
<router-link to="/profile" class="cc-btn" style="text-decoration:none">资料</router-link>
```
放在 Dock 组件退出按钮之前(props 不变,写在 Dock.vue 模板里)。

- [ ] **Step 5: 手动联调 + 构建 + 提交**

```bash
pnpm --dir frontend build && pnpm --dir frontend test
git add frontend/ && git commit -m "feat: 短语管理页+老师资料(办公室/播报模板)"
```

---

### Task 15: 显示端大屏 + 主题圆形揭示

**Files:**
- Modify: `frontend/src/views/DisplayView.vue`(替换占位)
- Modify: `frontend/src/composables/useDark.ts`(圆形揭示)
- Create: `frontend/src/components/ClassPicker.vue`

**Interfaces:**
- Consumes: `connectWS`、`api.classes`、bridge `speak/fullscreen`
- Produces: 显示端;`useDark().toggleDark(event)`(View Transition 圆形揭示,老师端 Dock 复用)

- [ ] **Step 1: 升级 `useDark.ts`**

```ts
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
  function forceDark() { apply(true) }
  return { isDark, initTheme, toggleDark, forceDark }
}
```

- [ ] **Step 2: `ClassPicker.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ picked: [classId: number, className: string] }>()
const classes = ref<{ id: number; name: string }[]>([])
onMounted(async () => { classes.value = await api.classes() })
</script>

<template>
  <div h-full flex="~ col items-center justify-center" gap-6>
    <h1 text-28px font-600 m-0>本教室是哪个班?</h1>
    <div grid="~ cols-3 gap-3" w-560px>
      <button v-for="c in classes" :key="c.id" class="glass-card" p-6 text-18px
              style="cursor:pointer" @click="emit('picked', c.id, c.name)">
        {{ c.name }}
      </button>
    </div>
    <p text-13px style="color: var(--cc-text-3)">选择后本机将记住,可在设置中修改</p>
  </div>
</template>
```

- [ ] **Step 3: `DisplayView.vue`**

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type CallItem } from '../api'
import { connectWS } from '../ws'
import ClassPicker from '../components/ClassPicker.vue'
import { useDark } from '../composables/useDark'

const { forceDark } = useDark()
const classId = Number(localStorage.getItem('cc_class')) || null
const className = ref(localStorage.getItem('cc_class_name') || '')
const picked = ref(classId !== null)
const cards = ref<CallItem[]>([])
const marquee = ref<CallItem[]>([])
const online = ref(false)
const clock = ref('')
let ws: ReturnType<typeof connectWS> | null = null
let timer: number | undefined

function tick() {
  clock.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function onPicked(id: number, name: string) {
  localStorage.setItem('cc_class', String(id))
  localStorage.setItem('cc_class_name', name)
  className.value = name
  picked.value = true
  ws?.subscribe(id)
}

onMounted(() => {
  forceDark()
  tick(); timer = window.setInterval(tick, 1000)
  ws = connectWS({
    classId: classId ?? undefined,
    onStatus: v => (online.value = v),
    onCall: (call) => {
      cards.value = [call, ...cards.value].slice(0, 3)
      marquee.value = [call, ...marquee.value].slice(0, 30)
      window.pywebview?.api?.speak?.(call.announce)
    },
    onRetract: (id) => {
      cards.value = cards.value.filter(c => c.id !== id)
      marquee.value = marquee.value.filter(c => c.id !== id)
    },
  })
})
onUnmounted(() => { ws?.close(); clearInterval(timer) })

const bigMsg = computed(() => (cards.value[0]?.message || '').split(','))
</script>

<template>
  <div v-if="!picked"><ClassPicker @picked="onPicked" /></div>
  <div v-else h-full flex="~ col" overflow-hidden pos-relative>
    <!-- 顶栏:班级+时钟+状态 -->
    <header flex="~ items-center" justify-between px-10 py-6>
      <span text-20px font-600>{{ className }}</span>
      <span text-20px font-300 style="font-variant-numeric: tabular-nums">{{ clock }}</span>
      <span text-13px :style="{ color: online ? 'var(--cc-theme)' : 'var(--cc-text-4)' }">
        {{ online ? '● 已连接' : '○ 连接中断,自动重连中…' }}
      </span>
    </header>

    <!-- 当前叫号 hero 卡 -->
    <main flex-1 flex="~ col items-center justify-center" gap-6 px-10>
      <TransitionGroup name="hero">
        <section v-if="cards[0]" :key="cards[0].id" class="glass-card"
                 w-min-720px px-16 py-12 flex="~ col items-center" gap-4>
          <div text-16px style="color: var(--cc-text-3)">请以下同学到</div>
          <div text="12vw leading-1" font-700>{{ cards[0].student_name }}</div>
          <div text-24px>{{ cards[0].teacher_name }} · {{ cards[0].office }}</div>
          <div v-if="bigMsg.length" flex="~ wrap justify-center gap-2" mt-2>
            <span v-for="m in bigMsg" :key="m" class="cc-chip" text-16px py-1 px-4>✚ {{ m }}</span>
          </div>
        </section>
      </TransitionGroup>
      <div v-if="!cards.length" text-18px style="color: var(--cc-text-3)">
        暂无叫号 · 请留意播报
      </div>
    </main>

    <!-- 走马灯 -->
    <footer h-56px flex="~ items-center" overflow-hidden px-10
            style="border-top: 1px solid var(--cc-border)">
      <div class="marquee" flex="~ gap-8" text-15px whitespace-nowrap>
        <span v-for="c in marquee" :key="c.id">
          <b>{{ c.student_name }}</b>
          <span style="color: var(--cc-text-3)">{{ c.created_at.slice(11, 16) }}</span>
        </span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.hero-enter-active { transition: all var(--cc-dur-slow) var(--cc-ease-overshoot); }
.hero-enter-from { opacity: 0; transform: translateY(40px) scale(0.96); }
.hero-leave-active { transition: all var(--cc-dur-fast) ease; position: absolute; }
.hero-leave-to { opacity: 0; }
.marquee { animation: scroll 24s linear infinite; }
@keyframes scroll {
  from { transform: translateX(100vw); }
  to { transform: translateX(-100%); }
}
</style>
```

- [ ] **Step 4: 三进程联调(带声音)**

```bash
sudo pacman -S espeak-ng   # 若未装
TTS=espeak ../.venv/bin/python -m app.main --role display --dev
# 另开:server(终端1,若未跑)、teacher(浏览器 http://127.0.0.1:5173/#/teacher)
```
Expected: 显示端选班 → 老师叫号 → 大屏卡片滑入 + espeak 播两遍;撤销后卡片消失;杀 server → 显示"连接中断" → 重启 server → 自动恢复订阅

- [ ] **Step 5: 构建 + 提交**

```bash
pnpm --dir frontend build && pnpm --dir frontend test
git add frontend/ && git commit -m "feat: 显示端大屏(hero 卡+走马灯+时钟)+ 主题圆形揭示"
```

---

### Task 16: 管理后台 + 服务器引导页

**Files:**
- Modify: `frontend/src/views/AdminView.vue`、`frontend/src/views/ServerView.vue`(替换占位)

**Interfaces:**
- Consumes: `api.bootstrapStatus/bootstrapAdmin/admin.*`
- Produces: 管理后台(老师/班级/历史 三标签);服务器模式首页(首次建管理员 → 状态页)

- [ ] **Step 1: `ServerView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, token } from '../api'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

const needsAdmin = ref<boolean | null>(null)
const info = ref<{ version: string; displays: number } | null>(null)
const username = ref(''); const password = ref('')
const { push } = useToast()

async function refresh() {
  needsAdmin.value = null
  const st = await api.bootstrapStatus()
  if (st.needs_admin) { needsAdmin.value = true; return }
  needsAdmin.value = false
  if (token.get()) {
    try { info.value = await api.admin.serverInfo() } catch { info.value = null }
  }
}
onMounted(refresh)

async function createAdmin() {
  try {
    const r = await api.bootstrapAdmin(username.value.trim(), password.value)
    token.set(r.token); push('管理员已创建')
    await refresh()
  } catch (e: any) { push(`创建失败:${e.message}`) }
}
</script>

<template>
  <div max-w-640px mx-auto px-6 py-10>
    <!-- 首次:创建管理员 -->
    <form v-if="needsAdmin" class="glass-card" p-8 flex="~ col gap-4" @submit.prevent="createAdmin">
      <h1 text-22px font-600 m-0>初始化服务器</h1>
      <p text-13px m-0 style="color: var(--cc-text-3)">首次使用,请创建管理员账号</p>
      <input v-model="username" class="cc-input" placeholder="管理员用户名">
      <input v-model="password" class="cc-input" type="password" placeholder="密码(至少 6 位)">
      <button class="cc-btn cc-btn-primary">创建</button>
    </form>

    <!-- 状态页 -->
    <div v-else-if="needsAdmin === false" class="glass-card" p-8 flex="~ col gap-4">
      <h1 text-22px font-600 m-0>服务器运行中</h1>
      <div flex="~ justify-between"><span style="color:var(--cc-text-3)">版本</span><b>v{{ info?.version ?? '—' }}</b></div>
      <div flex="~ justify-between"><span style="color:var(--cc-text-3)">在线显示端</span><b>{{ info?.displays ?? '—' }}</b></div>
      <p text-13px m-0 style="color: var(--cc-text-3)">
        老师端与显示端在局域网内自动发现本服务器,无需配置。
      </p>
      <a href="#/login" class="cc-btn cc-btn-primary" style="text-decoration:none; text-align:center">
        进入管理后台
      </a>
    </div>
    <Toasts />
  </div>
</template>
```

- [ ] **Step 2: `AdminView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, token } from '../api'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

type Teacher = { id: number; username: string; role: string; display_name: string; office: string; disabled: number }
type Cls = { id: number; name: string; ord: number }

const tab = ref<'teachers' | 'classes' | 'history'>('teachers')
const teachers = ref<Teacher[]>([])
const classes = ref<Cls[]>([])
const history = ref<Awaited<ReturnType<typeof api.admin.history>>['calls']>([])
const { push } = useToast()

const nt = { username: '', password: '', display_name: '', office: '' }
const newTeacher = ref({ ...nt })
const newClass = ref('')
const importText = ref('')
const importTarget = ref<number | null>(null)
const historyDate = ref(new Date().toISOString().slice(0, 10))

async function refresh() {
  if (tab.value === 'teachers') teachers.value = await api.admin.teachers() as any
  else if (tab.value === 'classes') classes.value = await api.classes() as any
  else history.value = (await api.admin.history(historyDate.value)).calls
}
onMounted(async () => {
  if (!token.get()) return location.assign('#/login')
  try { await refresh() } catch { /* 401 已跳转 */ }
})

async function addTeacher() {
  await api.admin.addTeacher({ ...newTeacher.value })
  newTeacher.value = { ...nt }; push('老师已添加'); await refresh()
}
async function addClass() {
  await api.admin.addClass(newClass.value.trim())
  newClass.value = ''; push('班级已添加'); await refresh()
}
async function importStudents() {
  if (!importTarget.value) return
  const r = await api.admin.importStudents(importTarget.value, importText.value)
  importText.value = ''
  push(`导入 ${r.imported} 人${r.skipped.length ? `,跳过 ${r.skipped.join('、')}` : ''}`)
}
</script>

<template>
  <div max-w-980px mx-auto px-6 py-6>
    <header flex="~ items-center justify-between" mb-4>
      <h1 text-20px font-600 m-0>管理后台</h1>
      <div flex gap-2>
        <button v-for="t in (['teachers','classes','history'] as const)" :key="t"
                :class="['cc-btn', { 'cc-btn-primary': tab === t }]" @click="tab = t; refresh()">
          {{ { teachers: '老师', classes: '班级', history: '历史' }[t] }}
        </button>
        <a href="#/login" class="cc-btn" style="text-decoration:none">退出</a>
      </div>
    </header>

    <!-- 老师 -->
    <section v-if="tab === 'teachers'" class="glass-card" p-4 flex="~ col gap-3">
      <div class="glass-card" p-3 flex="~ items-end gap-2" style="background: var(--cc-fill-1)">
        <input v-model="newTeacher.username" class="cc-input" placeholder="用户名">
        <input v-model="newTeacher.password" class="cc-input" type="password" placeholder="密码">
        <input v-model="newTeacher.display_name" class="cc-input" placeholder="称呼(郑老师)">
        <input v-model="newTeacher.office" class="cc-input" placeholder="办公室">
        <button class="cc-btn cc-btn-primary" @click="addTeacher">添加</button>
      </div>
      <div v-for="t in teachers" :key="t.id" flex="~ items-center gap-3" px-2 py-1>
        <b>{{ t.display_name || t.username }}</b>
        <span class="cc-chip" v-if="t.role === 'admin'">管理员</span>
        <span text-13px style="color:var(--cc-text-3)">{{ t.username }} · {{ t.office }}</span>
        <span flex-1 />
        <button v-if="!t.disabled" class="cc-btn" text-13px
                @click="api.admin.updateTeacher(t.id, { disabled: 1 }).then(refresh)">停用</button>
        <button v-else class="cc-btn" text-13px
                @click="api.admin.updateTeacher(t.id, { disabled: 0 }).then(refresh)">启用</button>
      </div>
    </section>

    <!-- 班级 -->
    <section v-else-if="tab === 'classes'" flex="~ col gap-3">
      <div class="glass-card" p-4 flex="~ items-center gap-2">
        <input v-model="newClass" class="cc-input" placeholder="新班级名,如 高二(3)班"
               @keydown.enter="addClass">
        <button class="cc-btn cc-btn-primary" @click="addClass">添加</button>
      </div>
      <div v-for="c in classes" :key="c.id" class="glass-card" p-4 flex="~ col gap-2">
        <div flex="~ items-center gap-3">
          <b text-16px>{{ c.name }}</b>
          <span flex-1 />
          <button class="cc-btn" text-13px
                  @click="api.admin.delClass(c.id).then(refresh)">删除班级</button>
        </div>
        <div flex="~ items-end gap-2">
          <textarea v-model="importText" class="cc-input" flex-1 rows-3
                    placeholder="粘贴学生名单,每行一个(可带学号:梁皓文 0305)" />
          <button class="cc-btn cc-btn-primary" @click="importTarget = c.id; importStudents()">
            导入名单
          </button>
        </div>
      </div>
    </section>

    <!-- 历史 -->
    <section v-else class="glass-card" p-4 flex="~ col gap-1">
      <div flex="~ items-center justify-between" mb-2>
        <input v-model="historyDate" class="cc-input" type="date" @change="refresh">
      </div>
      <div v-for="c in history" :key="c.id" flex="~ items-center gap-3" px-2 py-1 text-14px>
        <span w-64px style="color:var(--cc-text-3)">{{ c.created_at.slice(11, 16) }}</span>
        <b>{{ c.student_name }}</b>
        <span style="color:var(--cc-text-3)">{{ c.class_name }}</span>
        <span class="cc-chip" v-if="c.message">{{ c.message }}</span>
        <span flex-1 />
        <span text-12px style="color:var(--cc-text-3)">{{ c.teacher_name }}</span>
        <span v-if="c.retracted_at" class="cc-chip" style="color:var(--cc-text-4)">已撤销</span>
      </div>
      <div v-if="!history.length" px-2 py-4 text-13px style="color:var(--cc-text-4)">当日无记录</div>
    </section>
    <Toasts />
  </div>
</template>
```

- [ ] **Step 3: 全链路手动验收**

```bash
# 1. 删库重走首启流程
rm -rf data/
TTS=none ../.venv/bin/python -m app.main --role server --dev
# 2. 窗口里创建管理员 → 进管理后台 → 建老师(郑老师/203办公室)→ 建班级 → 粘贴导入名单
# 3. 开显示端(另一窗口 --role display --dev)选班级
# 4. 浏览器登录郑老师 → 敲 lhw → 回车 → 回车
```
Expected: 显示端大字+espeak 声;管理后台历史可见;老师端今日列表可见;明暗切换为圆形扩散

- [ ] **Step 4: 构建 + 提交**

```bash
pnpm --dir frontend build && pnpm --dir frontend test
git add frontend/ && git commit -m "feat: 管理后台(老师/班级导入/历史)+ 服务器引导页"
```

---

## Phase 2 验收清单

- [ ] `pytest -v` 与 `pnpm --dir frontend test` 全绿;`pnpm --dir frontend build` 0 错误
- [ ] 三进程联调:建管理员→建老师→导名单→叫号→大屏出字出声→撤销→历史可见
- [ ] 杀服务器:显示端显示断线 → 重启后自动恢复
- [ ] 主题切换为圆形揭示;显示端始终深色
- [ ] `git diff docs/CONTRACTS.md` 仅含 v1.1 增补
