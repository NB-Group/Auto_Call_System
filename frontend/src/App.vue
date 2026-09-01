<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useDark } from './composables/useDark'

const { initTheme } = useDark()
const update = ref<{ version: string; notes: string } | null>(null)
const restart = () => (window as any).pywebview?.api?.quit?.()

onMounted(() => {
  initTheme()
  window.addEventListener('cc-update', (ev) => {
    update.value = (ev as CustomEvent).detail
  })
})
</script>

<template>
  <router-view />
  <!-- left-1/2 translate-x--1/2 含 '/',SFC 解析器拒绝出现在属姓名中,改显式 style(同 Toasts) -->
  <div v-if="update" class="glass-pop" fixed top-4 z-50 text-14px
       style="left: 50%; transform: translateX(-50%)"
       px-5 py-3 flex="~ items-center gap-3">
    <span>新版本 v{{ update.version }} 已就绪,重启后生效</span>
    <button class="cc-btn cc-btn-primary" py-1 @click="restart">立即重启</button>
  </div>
</template>
