<script setup lang="ts">
import { useRouter } from 'vue-router'
import { api, token } from '../api'

defineProps<{ name: string; office: string }>()
const router = useRouter()

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
    <router-link to="/snippets" class="cc-btn" style="text-decoration:none">短语</router-link>
    <router-link to="/profile" class="cc-btn" style="text-decoration:none">资料</router-link>
    <button class="cc-btn" @click="logout">退出</button>
  </header>
</template>
