<script setup lang="ts">
import { useRouter } from 'vue-router'
import { api, token } from '../api'

defineProps<{ name: string; office: string }>()
const router = useRouter()

// B1:短语/资料曾用 <router-link>(渲染为 <a href="#/…">),真机 pywebview GTK
// 上报点不动。jsdom 整链测试(Dock.test.ts)与 WebKitGTK 真窗探针
// (scripts/diag_b1_dock_click.py:elementFromPoint 命中自身、合成点击全链通)
// 均复现不了 —— 真凶更可能是窗口长跑期间 dist 重建、旧 chunk 名 404 导致
// 路由静默中止(重开窗已验证正常)。防御性收敛:弃 anchor 走 button +
// router.push,绕开 WebView 里 <a> 默认动作的一切怪癖,行为与「退出」钮一致。
async function logout() {
  try { await api.logout() } catch { /* 忽略 */ }
  token.clear()
  router.replace('/login')
}
</script>

<template>
  <!-- Task-21:品牌(● 叫号中心)与主题切换钮移入全局 TitleBar,此处只留身份与导航 -->
  <header class="glass-card" flex="~ items-center gap-3" h-64px px-6 mb-6>
    <div flex-1 flex="~ items-center gap-2" text-15px>
      <b>{{ name }}</b>
      <span text-13px style="color: var(--cc-text-3)">{{ office }}</span>
    </div>
    <button class="cc-btn" @click="router.push('/snippets')">短语</button>
    <button class="cc-btn" @click="router.push('/profile')">资料</button>
    <button class="cc-btn" @click="logout">退出</button>
  </header>
</template>
