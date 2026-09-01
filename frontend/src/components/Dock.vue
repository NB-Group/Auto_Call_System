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
    <!-- 方法引用绑定:click 事件作为 toggleDark(ev) 首参 → 圆形揭示以按钮为圆心 -->
    <button class="cc-btn" title="切换主题" @click="toggleDark">
      {{ isDark ? '☀️' : '🌙' }}
    </button>
    <router-link to="/snippets" class="cc-btn" style="text-decoration:none">短语</router-link>
    <router-link to="/profile" class="cc-btn" style="text-decoration:none">资料</router-link>
    <button class="cc-btn" @click="logout">退出</button>
  </header>
</template>
