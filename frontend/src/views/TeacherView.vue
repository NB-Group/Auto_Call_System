<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, token, type CallItem, type MeInfo } from '../api'
import Dock from '../components/Dock.vue'
import Palette from '../components/Palette.vue'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'
import { groupCalls } from '../callGroups'

const me = ref<MeInfo | null>(null)
const today = ref<CallItem[]>([])
const { push } = useToast()
const now = ref(Date.now())
setInterval(() => (now.value = Date.now()), 1000)

// Task-21「一批一行」:Palette 连发 N 条同批叫号,今日列表按 4s 窗口聚成
// 一行(显示端聚合窗 1.2s 只覆盖广播突发,老师手点间隔更宽,取更宽窗)。
const TODAY_GROUP_MS = 4000
const groups = computed(() => groupCalls(today.value, TODAY_GROUP_MS))

async function refresh() { today.value = (await api.today()).calls }
onMounted(async () => {
  if (!token.get()) return location.assign('#/login')
  try { me.value = await api.me() } catch { return }
  await refresh()
})

// 批量撤销:逐条顺序调 undo(服务端按条校验 60s 窗),按成功数汇报。
const undoing = ref(false)
async function undoBatch(g: CallItem[]) {
  if (undoing.value) return
  undoing.value = true
  let ok = 0
  for (const c of g) {
    try { await api.undo(c.id); ok++ } catch { /* 计数继续 */ }
  }
  undoing.value = false
  await refresh()
  if (ok === g.length) push(`已撤销 ${ok} 条`)
  else if (ok === 0) push('撤销失败:超过 60 秒')
  else push(`部分成功:已撤销 ${ok}/${g.length} 条`)
}

const undoable = (c: CallItem) =>
  !c.retracted_at && now.value - new Date(c.created_at.replace(' ', 'T')).getTime() < 60000
// 整批都还在各自 60s 窗内才给批撤销(部分过期时逐条结果混乱,宁可不给)
const batchUndoable = (g: CallItem[]) => g.every(undoable)
const allRetracted = (g: CallItem[]) => g.every(c => c.retracted_at)
</script>

<template>
  <div v-if="me" max-w-880px mx-auto px-6 py-6 min-h-full>
    <Dock :name="me.display_name" :office="me.office" />
    <Palette @sent="refresh" />
    <section mt-6>
      <h2 text-14px font-600 style="color: var(--cc-text-2)">今日已叫({{ today.length }})</h2>
      <div class="glass-card" mt-3 p-2 flex="~ col" pos-relative>
        <TransitionGroup name="list">
          <div v-for="(g, i) in groups" :key="g[0].id" :style="{ '--stagger': Math.min(i, 8) }"
               flex="~ items-center gap-3" px-3 py-2>
            <span w-64px text-13px style="color: var(--cc-text-3)">{{ g[0].created_at.slice(11, 16) }}</span>
            <b>{{ g.map(c => c.student_name).join('、') }}</b>
            <span text-12px style="color: var(--cc-text-3)">{{ g[0].class_name }}</span>
            <span v-if="g[0].message" class="cc-chip">{{ g[0].message }}</span>
            <span v-if="allRetracted(g)" text-12px style="color: var(--cc-text-4)">已撤销</span>
            <span flex-1 />
            <button v-if="batchUndoable(g)" class="cc-btn" text-13px :disabled="undoing"
                    @click="undoBatch(g)">撤销{{ g.length > 1 ? ` ${g.length} 条` : '' }}</button>
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
