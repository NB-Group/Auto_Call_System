<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type CallItem, type Snippet, type StudentHit } from '../api'
import { initial, reduce, type PaletteState, type SendEffect } from '../palette'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ sent: [call: CallItem] }>()
const { push } = useToast()

const state = ref<PaletteState>({ ...initial })
const students = ref<StudentHit[]>([])
const snippets = ref<Snippet[]>([])
const inputEl = ref<HTMLInputElement | null>(null)
const listEl = ref<HTMLElement | null>(null)

const results = computed(() =>
  state.value.phase === 'student'
    ? students.value.map(s => ({ key: s.id, title: s.name, sub: s.class_name }))
    : snippets.value.map(s => ({ key: s.id, title: s.text, sub: `×${s.use_count}` })))

let searchSeq = 0
watch(() => [state.value.phase, state.value.query] as const, async ([phase, q]) => {
  if (phase === 'compose' && state.value.freeText) { students.value = []; snippets.value = []; return }
  const seq = ++searchSeq
  if (!q.trim()) {
    if (phase === 'student') students.value = []
    else snippets.value = await api.searchSnippets('')
    return
  }
  const res = phase === 'student'
    ? await api.searchStudents(q).catch(() => [])
    : await api.searchSnippets(q).catch(() => [])
  if (seq === searchSeq) {
    if (phase === 'student') students.value = res as StudentHit[]
    else snippets.value = res as Snippet[]
  }
})

function dispatch(e: Parameters<typeof reduce>[1]) {
  const { state: next, effect } = reduce(state.value, e)
  state.value = next
  if (effect) void send(effect)
}
async function send(effect: SendEffect) {
  try {
    const { call } = await api.call(
      effect.student.id, effect.snippetIds, effect.freeText)
    push(`已呼叫 ${effect.student.name} · ${call.class_name}`)
    emit('sent', call)
  } catch (e: any) {
    push(`发送失败:${e.message}`)
    state.value = { ...initial, student: effect.student, phase: 'compose' }
  }
}
function pick(i: number) {
  state.value.activeIndex = i
  dispatch({ t: 'enter', students: students.value, snippets: snippets.value })
}

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === 'ArrowDown') { dispatch({ t: 'down' }); ev.preventDefault() }
  else if (ev.key === 'ArrowUp') { dispatch({ t: 'up' }); ev.preventDefault() }
  else if (ev.key === 'Enter') {
    dispatch({ t: 'enter', students: students.value, snippets: snippets.value })
    ev.preventDefault()
  }
  else if (ev.key === 'Tab') { dispatch({ t: 'tab' }); ev.preventDefault() }
  else if (ev.key === 'Escape') dispatch({ t: 'esc' })
  else if (ev.key === 'Backspace') dispatch({ t: 'backspace' })
  else if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey) dispatch({ t: 'type', ch: ev.key })
}

watch(() => state.value.activeIndex, () => {
  listEl.value?.querySelector('.active')?.scrollIntoView({ block: 'nearest' })
})
onMounted(() => inputEl.value?.focus())

const PLACEHOLDER = computed(() =>
  state.value.phase === 'student'
    ? '输入姓名或拼音(如 lhw)…'
    : state.value.freeText ? '自由输入附加消息,回车发送…'
    : '选短语(如 dz)回车挂载 · Tab 自由输入 · 直接回车发送')
</script>

<template>
  <div class="glass-card" p-4 pos-relative @mousedown="inputEl?.focus()">
    <!-- 已选学生与 chips -->
    <div v-if="state.phase === 'compose'" flex="~ items-center gap-2 wrap" mb-3 text-15px>
      <span class="cc-chip" font-600 text-15px style="background: var(--cc-theme); color: #fff; border-color: transparent">
        {{ state.student?.name }}
      </span>
      <span v-for="c in state.chips" :key="c.id" class="cc-chip">✚ {{ c.text }}</span>
      <span v-if="state.freeText" text-12px style="color: var(--cc-text-4)">自由输入</span>
    </div>

    <input ref="inputEl" :value="state.query" class="cc-input w-full text-17px"
           :placeholder="PLACEHOLDER" mb-2 autocomplete="off" spellcheck="false"
           @keydown="onKeydown">

    <div ref="listEl" max-h-320px overflow-auto flex="~ col gap-1">
      <div v-for="(r, i) in results" :key="r.key"
           :class="['result', { active: i === Math.min(state.activeIndex, results.length - 1) }]"
           flex="~ items-center justify-between" px-3 py-2 rounded-8px cursor-pointer
           @click="pick(i)">
        <span>{{ r.title }}</span>
        <span text-12px style="color: var(--cc-text-3)">{{ r.sub }}</span>
      </div>
      <div v-if="!results.length && (state.query || state.phase === 'student')"
           px-3 py-2 text-13px style="color: var(--cc-text-4)">
        {{ state.phase === 'student' ? '开始输入以搜索学生' : '无匹配短语 · 回车将作为自由文本发送' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.result.active { background: var(--cc-theme-10); }
.result:hover { background: var(--cc-fill-1); }
input { border: none; background: transparent; padding-left: 4px; }
input:focus { box-shadow: none; border: none; }
</style>
