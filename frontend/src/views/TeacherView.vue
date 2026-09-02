<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, token, type CallItem, type MeInfo } from '../api'
import Dock from '../components/Dock.vue'
import Palette from '../components/Palette.vue'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

const me = ref<MeInfo | null>(null)
const today = ref<CallItem[]>([])
const { push } = useToast()
const now = ref(Date.now())
setInterval(() => (now.value = Date.now()), 1000)

async function refresh() { today.value = (await api.today()).calls }
onMounted(async () => {
  if (!token.get()) return location.assign('#/login')
  try { me.value = await api.me() } catch { return }
  await refresh()
})

async function undo(c: CallItem) {
  try { await api.undo(c.id); await refresh(); push(`已撤销 ${c.student_name}`) }
  catch (e: any) { push(`撤销失败:${e.message === 'gone' ? '超过 60 秒' : e.message}`) }
}
const undoable = (c: CallItem) =>
  !c.retracted_at && now.value - new Date(c.created_at.replace(' ', 'T')).getTime() < 60000
</script>

<template>
  <div v-if="me" max-w-880px mx-auto px-6 py-6 min-h-full>
    <Dock :name="me.display_name" :office="me.office" />
    <Palette @sent="refresh" />
    <section mt-6>
      <h2 text-14px font-600 style="color: var(--cc-text-2)">今日已叫({{ today.length }})</h2>
      <div class="glass-card" mt-3 p-2 flex="~ col" pos-relative>
        <TransitionGroup name="list">
          <div v-for="(c, i) in today" :key="c.id" :style="{ '--stagger': Math.min(i, 8) }"
               flex="~ items-center gap-3" px-3 py-2>
            <span w-64px text-13px style="color: var(--cc-text-3)">{{ c.created_at.slice(11, 16) }}</span>
            <b>{{ c.student_name }}</b>
            <span text-12px style="color: var(--cc-text-3)">{{ c.class_name }}</span>
            <span v-if="c.message" class="cc-chip">{{ c.message }}</span>
            <span v-if="c.retracted_at" text-12px style="color: var(--cc-text-4)">已撤销</span>
            <span flex-1 />
            <button v-if="undoable(c)" class="cc-btn" text-13px @click="undo(c)">撤销</button>
          </div>
        </TransitionGroup>
        <div v-if="!today.length" px-3 py-4 text-13px style="color: var(--cc-text-4)">
          还没有叫号记录,从上方搜索开始 ⌘
        </div>
      </div>
    </section>
    <Toasts />
  </div>
</template>

<style scoped>
/* 今日列表:FLIP 平移 + 行入场错峰淡入 */
.list-move { transition: transform var(--cc-dur-cozy) var(--cc-ease-smooth); }
.list-enter-active {
  transition: all var(--cc-dur-cozy) var(--cc-ease-smooth);
  transition-delay: calc(var(--stagger, 0) * 28ms);
}
.list-enter-from { opacity: 0; transform: translateY(10px); }
.list-leave-active { transition: all var(--cc-dur-fast) ease; position: absolute; }
.list-leave-to { opacity: 0; }
</style>
