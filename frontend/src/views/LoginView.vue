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
