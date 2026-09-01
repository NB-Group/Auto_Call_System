<script setup lang="ts">
import { useToast } from '../composables/useToast'
const { toasts } = useToast()
</script>

<template>
  <!-- 左右居中:left-1/2 / translate-x--1/2 含 '/',SFC 解析器拒绝出现在属姓名中,改显式 style -->
  <div fixed bottom-6 z-50 style="left: 50%; transform: translateX(-50%)" flex="~ col gap-2">
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
