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
    <!-- useDark().toggleDark 为 0 参函数,直接绑定方法引用 -->
    <button class="cc-btn" title="切换主题" @click="toggleDark">
      {{ isDark ? '☀️' : '🌙' }}
    </button>
    <button class="cc-btn" @click="logout">退出</button>
  </header>
</template>
