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
      <div v-for="(s, i) in items" :key="s.id" class="cc-stagger cc-row-hover"
           :style="{ '--stagger': Math.min(i, 8) }" flex="~ items-center gap-3" px-3 py-2 rounded-8px>
        <span class="cc-chip">✚ {{ s.text }}</span>
        <span text-12px style="color: var(--cc-text-3)">用了 {{ s.use_count }} 次</span>
        <span flex-1 />
        <button class="cc-btn" text-13px @click="del(s.id)">删除</button>
      </div>
      <div v-if="!items.length" class="cc-float" px-3 py-4 text-13px style="color: var(--cc-text-4)">
        还没有短语。添加几条常用的,叫号时敲首字母就能挂上。
      </div>
    </div>
    <Toasts />
  </div>
</template>
