<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ picked: [classId: number, className: string] }>()
const classes = ref<{ id: number; name: string }[]>([])
const failed = ref(false)

async function load() {
  failed.value = false
  try { classes.value = await api.classes() }
  catch { failed.value = true }
}
onMounted(load)
</script>

<template>
  <div h-full flex="~ col items-center justify-center" gap-6>
    <h1 text-28px font-600 m-0>本教室是哪个班?</h1>
    <template v-if="failed">
      <!-- 加载失败:给出可重试的错误态,而非空白网格(Task-16 context C) -->
      <p text-14px m-0 style="color: var(--cc-theme)">加载班级失败,请检查服务器连接</p>
      <button class="cc-btn" @click="load">重试</button>
    </template>
    <template v-else>
      <div grid="~ cols-3 gap-3" w-560px>
        <button v-for="(c, i) in classes" :key="c.id" class="glass-card cls-in" p-6 text-18px
                :style="{ '--stagger': Math.min(i, 8), cursor: 'pointer' }"
                @click="emit('picked', c.id, c.name)">
          {{ c.name }}
        </button>
      </div>
      <p text-13px style="color: var(--cc-text-3)">选择后本机将记住,可在设置中修改</p>
    </template>
  </div>
</template>

<style scoped>
/* Task-22:班级卡逐格弹入 + hover 抬升放大 */
.cls-in {
  animation: cls-in var(--cc-dur-cozy) var(--cc-ease-overshoot) backwards;
  animation-delay: calc(var(--stagger, 0) * var(--cc-stagger-step));
  transition: transform var(--cc-dur-fast) var(--cc-ease-smooth),
    box-shadow var(--cc-dur-fast) var(--cc-ease-smooth);
}
@keyframes cls-in {
  from { opacity: 0; transform: scale(0.8); }
  to { opacity: 1; transform: none; }
}
.cls-in:hover { transform: translateY(-3px) scale(1.03); box-shadow: var(--cc-shadow-2); }
.cls-in:active { transform: translateY(0) scale(0.97); }
@media (prefers-reduced-motion: reduce) {
  .cls-in { animation: none; }
}
</style>
