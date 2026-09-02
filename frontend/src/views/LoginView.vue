<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, token } from '../api'

const router = useRouter()
const username = ref('')
const password = ref('')
const err = ref('')
const busy = ref(false)
const shaking = ref(false)

// 错误抖动:先摘 class 过一帧再挂回,同文案连错也能重触发
function reshake() {
  shaking.value = false
  requestAnimationFrame(() => requestAnimationFrame(() => (shaking.value = true)))
}

async function submit() {
  busy.value = true; err.value = ''
  try {
    const r = await api.login(username.value.trim(), password.value)
    token.set(r.token)
    router.replace(r.role === 'admin' ? '/admin' : '/teacher')
  } catch (e: any) {
    err.value = e.message === 'unauthorized' ? '用户名或密码错误' : e.message
    reshake()
  } finally { busy.value = false }
}
</script>

<template>
  <div h-full flex="~ items-center justify-center">
    <form class="glass-card card-in" :class="{ shake: shaking }" w-360px p-8 flex="~ col gap-4" @submit.prevent="submit">
      <h1 text-22px font-600 m-0 class="stagger" :style="{ '--stagger': 1 }">叫号中心</h1>
      <p text-13px m-0 class="stagger" :style="{ '--stagger': 2 }" style="color: var(--cc-text-3)">老师登录</p>
      <input v-model="username" class="cc-input stagger" :style="{ '--stagger': 3 }"
             placeholder="用户名" autocomplete="username">
      <input v-model="password" class="cc-input stagger" :style="{ '--stagger': 4 }" type="password"
             placeholder="密码" autocomplete="current-password">
      <div v-if="err" text-13px class="err-in" style="color: var(--cc-theme)">{{ err }}</div>
      <button class="cc-btn cc-btn-primary stagger" :style="{ '--stagger': 5 }" :disabled="busy" mt-2>
        <span v-if="busy" flex="~ inline items-center">登录中<span class="dots" /></span>
        <span v-else>登 录</span>
      </button>
    </form>
  </div>
</template>

<style scoped>
/* 卡片入场:上浮 24px + 淡入,回弹(时长走 --cc-dur-name) */
.card-in {
  animation: card-in var(--cc-dur-name) var(--cc-ease-overshoot) both;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: none; }
}
/* 子元素逐个错峰跟上(同面板的 --stagger 手法) */
.stagger {
  animation: rise-in var(--cc-dur-cozy) var(--cc-ease-smooth) both;
  animation-delay: calc(var(--stagger, 0) * 60ms);
}
@keyframes rise-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
/* Task-22:提交失败 → 整卡左右抖动;错误文案淡入上浮;按钮 busy 三点动画 */
.shake { animation: shake var(--cc-dur-slow) ease both; }
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  15% { transform: translateX(-10px); }
  30% { transform: translateX(9px); }
  45% { transform: translateX(-7px); }
  60% { transform: translateX(5px); }
  75% { transform: translateX(-3px); }
}
.err-in {
  animation: rise-in var(--cc-dur-cozy) var(--cc-ease-smooth) both;
}
.dots::after {
  content: '';
  animation: dots 1.2s steps(1) infinite;
}
@keyframes dots {
  0% { content: ''; }
  25% { content: '.'; }
  50% { content: '..'; }
  75%, 100% { content: '...'; }
}
@media (prefers-reduced-motion: reduce) {
  .card-in, .stagger, .shake, .err-in { animation: none; }
}
</style>
