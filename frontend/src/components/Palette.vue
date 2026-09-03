<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type Snippet, type StudentHit } from '../api'
import { initial, planKeydown, reduce, type PaletteState, type SendEffect } from '../palette'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ sent: [] }>()
const { push } = useToast()

const state = ref<PaletteState>({ ...initial })
const students = ref<StudentHit[]>([])
const snippets = ref<Snippet[]>([])
const inputEl = ref<HTMLInputElement | null>(null)
const listEl = ref<HTMLElement | null>(null)

const results = computed(() =>
  state.value.phase === 'student'
    ? students.value.map(s => ({
        key: s.id, title: s.name, sub: s.class_name,
        picked: state.value.picked.some(p => p.id === s.id),
      }))
    : snippets.value.map(s => ({ key: s.id, title: s.text, sub: `×${s.use_count}`, picked: false })))

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
// 多人叫号:逐个顺序呼叫(服务器/播报端按序处理),统计成功/失败
async function send(effect: SendEffect) {
  let ok = 0
  let fail = 0
  let lastErr = ''
  for (const st of effect.students) {
    try { await api.call(st.id, effect.snippetIds, effect.freeText); ok++ }
    catch (e: any) { fail++; lastErr = e?.message ?? '' }
  }
  if (ok > 0) {
    push(`已呼叫 ${ok} 名学生${fail ? `,失败 ${fail}` : ''}`)
    emit('sent')
  } else {
    push(`发送失败:${lastErr}`)
    // 全失败:退回拼装以便重试(保留目标学生与 chips 由重试者决定,先给回学生)
    state.value = { ...initial, phase: 'compose', students: effect.students }
  }
}
// 点结果行:选生阶段 = 空格同等的多选 toggle;拼装阶段 = 回车挂短语
function pick(i: number) {
  state.value.activeIndex = i
  if (state.value.phase === 'student')
    dispatch({ t: 'space', students: students.value })
  else
    dispatch({ t: 'enter', students: students.value, snippets: snippets.value })
}

function onKeydown(ev: KeyboardEvent) {
  // 映射纯函数在 palette.ts(planKeydown):IME 组合期放行、Ctrl+L 清空
  // 先于其余分支判定 —— 见其注释(guard 顺序说明)。这里只按 plan 派发。
  const plan = planKeydown(ev)
  if (!plan) return
  switch (plan.kind) {
    case 'clear': dispatch({ t: 'clear' }); ev.preventDefault(); return
    case 'down': dispatch({ t: 'down' }); ev.preventDefault(); return
    case 'up': dispatch({ t: 'up' }); ev.preventDefault(); return
    case 'enter':
      dispatch({ t: 'enter', students: students.value, snippets: snippets.value })
      ev.preventDefault()
      return
    case 'space':
      // 选生阶段空格 = 多选;拼装阶段空格是自由文本的一部分,放行
      if (state.value.phase === 'student') {
        dispatch({ t: 'space', students: students.value })
        ev.preventDefault()
      }
      return
    case 'tab': dispatch({ t: 'tab' }); ev.preventDefault(); return
    case 'esc': dispatch({ t: 'esc' }); return
    case 'backspace': dispatch({ t: 'backspace' }); return
  }
}

// 文本输入走 input 事件而非 keydown(keydown 在 IME 下拿不到拼音串)。
const composing = ref(false)
function onCompositionStart() { composing.value = true }
function onCompositionEnd(ev: CompositionEvent) {
  composing.value = false
  dispatch({ t: 'set', query: (ev.target as HTMLInputElement).value })
}
function onInput(ev: Event) {
  if (composing.value) return
  dispatch({ t: 'set', query: (ev.target as HTMLInputElement).value })
}

watch(() => state.value.activeIndex, () => {
  listEl.value?.querySelector('.active')?.scrollIntoView({ block: 'nearest' })
})
onMounted(() => inputEl.value?.focus())

const PLACEHOLDER = computed(() =>
  state.value.phase === 'student'
    ? '输入姓名或拼音(如 lhw),空格多选 · Ctrl+L 清空…'
    : state.value.freeText ? '自由输入附加消息,回车发送…'
    : '选短语(如 dz)回车挂载 · Tab 自由输入 · Ctrl+L 清空')
</script>

<template>
  <div class="glass-card" p-4 pos-relative @mousedown="inputEl?.focus()">
    <!-- 选生阶段:已多选学生 chips -->
    <TransitionGroup v-if="state.phase === 'student' && state.picked.length"
                     name="chip" tag="div" flex="~ items-center gap-2 wrap" mb-3 text-15px>
      <span v-for="p in state.picked" :key="`p-${p.id}`" class="cc-chip chip" font-600 cursor-pointer
            style="background: var(--cc-theme); color: #fff; border-color: transparent"
            @click="dispatch({ t: 'unpick', id: p.id })">
        {{ p.name }}<span class="chip-x">✕</span>
      </span>
    </TransitionGroup>

    <!-- 拼装阶段:全部目标学生 + 短语 chips -->
    <div v-if="state.phase === 'compose'" mb-3 text-15px>
      <TransitionGroup name="chip" tag="div" flex="~ items-center gap-2 wrap">
        <span v-for="st in state.students" :key="`s-${st.id}`" class="cc-chip chip" font-600 text-15px
              style="background: var(--cc-theme); color: #fff; border-color: transparent">
          {{ st.name }}
        </span>
        <span v-for="c in state.chips" :key="`c-${c.id}`" class="cc-chip chip">✚ {{ c.text }}</span>
      </TransitionGroup>
      <span v-if="state.freeText" text-12px style="color: var(--cc-text-4)">自由输入</span>
    </div>

    <input ref="inputEl" :value="state.query" class="cc-input w-full text-17px"
           :placeholder="PLACEHOLDER" mb-2 autocomplete="off" spellcheck="false"
           @keydown="onKeydown" @input="onInput"
           @compositionstart="onCompositionStart" @compositionend="onCompositionEnd">

    <!-- 选生阶段:操作提示 + 已选计数 -->
    <div v-if="state.phase === 'student'" flex="~ items-center justify-between" mb-1 px-1
         text-12px style="color: var(--cc-text-4)">
      <span>空格/点击 多选 · 回车 进入下一步</span>
      <span v-if="state.picked.length" style="color: var(--cc-theme)">
        已选 {{ state.picked.length }} 人
      </span>
    </div>

    <div ref="listEl" max-h-320px overflow-auto flex="~ col gap-1">
      <div v-for="(r, i) in results" :key="r.key" :style="{ '--stagger': Math.min(i, 8) }"
           :class="['result', 'row-in', { active: i === Math.min(state.activeIndex, results.length - 1) }]"
           flex="~ items-center justify-between" px-3 py-2 rounded-8px cursor-pointer
           @click="pick(i)">
        <span flex="~ items-center gap-2" :style="r.picked ? 'color: var(--cc-theme); font-weight: 600' : ''">
          <span v-if="r.picked">✓</span>{{ r.title }}
        </span>
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
/* 结果行:hover 右滑 4px;左侧主题色指示条 scaleX 0→1(origin left);active 主题色光晕 */
.result {
  position: relative;
  transition: background-color var(--cc-dur-fast) var(--cc-ease-smooth),
    box-shadow var(--cc-dur-fast) var(--cc-ease-smooth),
    transform var(--cc-dur-fast) var(--cc-ease-smooth);
}
.result::before {
  content: '';
  position: absolute; left: 0; top: 22%; bottom: 22%; width: 3px;
  border-radius: 999px; background: var(--cc-theme);
  transform: scaleX(0); transform-origin: left center;
  transition: transform var(--cc-dur-cozy) var(--cc-ease-overshoot);
}
.result:hover { background-color: var(--cc-fill-1); transform: translateX(4px); }
.result:hover::before, .result.active::before { transform: scaleX(1); }
.result.active {
  background-color: var(--cc-theme-10);
  box-shadow: 0 0 0 1px var(--cc-theme-20), 0 4px 14px var(--cc-theme-20);
}
input { border: none; background: transparent; padding-left: 4px; }
input:focus { box-shadow: none; border: none; }

/* 结果行入场:淡入 + 8px 上浮,按 --stagger 逐行错峰(≤8 行封顶)。
   fill 用 backwards:结束后不驻留 keyframe 终态,否则动画帧压过 hover 的 transform 过渡 */
.row-in {
  animation: row-in var(--cc-dur-cozy) var(--cc-ease-smooth) backwards;
  animation-delay: calc(var(--stagger, 0) * var(--cc-stagger-step));
}
@keyframes row-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}

/* chip 弹入:0.6→1 缩放 + 回弹;移除 = 抖动淡出(shake-fade);✕ hover 旋转 90° */
.chip-enter-active { transition: all var(--cc-dur-cozy) var(--cc-ease-overshoot); }
.chip-leave-active { animation: chip-out var(--cc-dur-cozy) var(--cc-ease-smooth) both; }
.chip-enter-from { opacity: 0; transform: scale(0.6); }
.chip-move { transition: transform var(--cc-dur-cozy) var(--cc-ease-smooth); }
@keyframes chip-out {
  0% { opacity: 1; transform: translateX(0) rotate(0deg) scale(1); }
  20% { opacity: 1; transform: translateX(-5px) rotate(-2.5deg) scale(1); }
  45% { opacity: .9; transform: translateX(5px) rotate(2.5deg) scale(.96); }
  70% { opacity: .6; transform: translateX(-3px) rotate(-1.5deg) scale(.9); }
  100% { opacity: 0; transform: translateX(0) rotate(0deg) scale(.7); }
}
.chip-x {
  display: inline-block; margin-left: 2px; font-weight: 400; opacity: .85;
  transition: transform var(--cc-dur-cozy) var(--cc-ease-overshoot);
}
.chip:hover .chip-x { transform: rotate(90deg) scale(1.15); opacity: 1; }
</style>
