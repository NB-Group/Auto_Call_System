<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type CallItem } from '../api'
import { connectWS } from '../ws'
import ClassPicker from '../components/ClassPicker.vue'
import { useDark } from '../composables/useDark'
import { GROUP_WINDOW_MS, closeExpired, initGroups, onCall, onRetract, type GroupsState } from '../callGroups'

const { forceDark } = useDark()
const classId = Number(localStorage.getItem('cc_class')) || null
const className = ref(localStorage.getItem('cc_class_name') || '')
const picked = ref(classId !== null)
const gs = ref<GroupsState>(initGroups())
const marquee = ref<CallItem[]>([])
const online = ref(false)
const clock = ref('')
let ws: ReturnType<typeof connectWS> | null = null
let timer: number | undefined
let sweepTimer: number | undefined

function tick() {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  clock.value = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function connect(sub?: number) {
  ws = connectWS({
    classId: sub,
    onStatus: v => (online.value = v),
    // 突发聚合:老师端循环 N 次 call → 服务端连发 N 条广播,同师同消息 1.2s 内聚一卡
    onCall: (call) => {
      gs.value = onCall(gs.value, call, Date.now())
      // 兜底清窗旗(时间检查本身会拦,这里只是让 closed 状态落定)
      clearTimeout(sweepTimer)
      sweepTimer = window.setTimeout(
        () => (gs.value = closeExpired(gs.value, Date.now())), GROUP_WINDOW_MS + 100)
      marquee.value = [call, ...marquee.value].slice(0, 30)
      window.pywebview?.api?.speak?.(call.announce)
    },
    onRetract: (id) => {
      gs.value = onRetract(gs.value, id)
      marquee.value = marquee.value.filter(c => c.id !== id)
    },
  })
}

function onPicked(id: number, name: string) {
  localStorage.setItem('cc_class', String(id))
  localStorage.setItem('cc_class_name', name)
  className.value = name
  picked.value = true
  if (ws) ws.subscribe(id)
  else connect(id) // 陈旧校验清除了记忆 → 此刻才建连
}

onMounted(async () => {
  forceDark()
  tick(); timer = window.setInterval(tick, 1000)
  // 陈旧班级校验(Task-15 review B):换库后记忆的 class_id 失配 → 清除并重选班级;
  // 拉取失败则保留记忆照常连接(离线韧性)。校验落地后才连 WS。
  if (classId !== null) {
    try {
      const list = await api.classes()
      if (!list.some(c => c.id === classId)) {
        localStorage.removeItem('cc_class')
        localStorage.removeItem('cc_class_name')
        className.value = ''
        picked.value = false
        return
      }
    } catch { /* 服务器暂不可达:按记忆直连,WS 自带重连 */ }
  }
  connect(classId ?? undefined)
})
onUnmounted(() => { ws?.close(); clearInterval(timer); clearTimeout(sweepTimer) })

const hero = computed(() => gs.value.groups[0] ?? null)
const historyGroups = computed(() => gs.value.groups.slice(1))
// 名字区字号自适应:1 人 12vw / 2-3 人 8vw / 4-6 人 6vw / 7+ 4.5vw
const sizeClass = computed(() => {
  const n = hero.value?.calls.length ?? 1
  if (n <= 1) return 'names-1'
  if (n <= 3) return 'names-2'
  if (n <= 6) return 'names-3'
  return 'names-4'
})
// filter(Boolean):message 为空('' .split(',') 得 [''])时不渲染空 chip
const bigMsg = computed(() => (hero.value?.calls[0].message || '').split(',').filter(Boolean))
</script>

<template>
  <div v-if="!picked"><ClassPicker @picked="onPicked" /></div>
  <div v-else h-full flex="~ col" overflow-hidden pos-relative>
    <!-- 顶栏:班级+时钟+状态 -->
    <header flex="~ items-center" justify-between px-10 py-6>
      <span text-20px font-600>{{ className }}</span>
      <!-- 冒号独立成 span:1s 脉冲闪烁,与秒走同步观感 -->
      <span text-20px font-300 style="font-variant-numeric: tabular-nums"><span
        v-for="(seg, i) in clock.split(':')" :key="i"><span v-if="i" class="colon">:</span>{{ seg }}</span></span>
      <span text-13px :style="{ color: online ? 'var(--cc-theme)' : 'var(--cc-text-4)' }">
        {{ online ? '● 已连接' : '○ 连接中断,自动重连中…' }}
      </span>
    </header>

    <!-- 当前叫号 hero 组卡(一卡多人)+ 历史组栈 -->
    <main flex-1 flex="~ col items-center justify-center" gap-4 px-10 overflow-hidden>
      <TransitionGroup name="hero">
        <section v-if="hero" :key="hero.id" class="glass-card breathe hero-card"
                 min-w-720px max-w-92vw px-12 py-10 flex="~ col items-center" gap-4>
          <div text-16px class="settle" style="color: var(--cc-text-3)">
            请以下同学到 <b>{{ hero.calls[0].teacher_name }}</b> · {{ hero.calls[0].office }}
          </div>
          <div :class="['names', sizeClass]" flex="~ wrap justify-center" style="gap: .4em">
            <TransitionGroup name="name">
              <div v-for="(c, i) in hero.calls" :key="c.id" class="name-blk"
                   :style="{ '--stagger': Math.min(i, 10) }">
                {{ c.student_name }}
              </div>
            </TransitionGroup>
          </div>
          <div v-if="bigMsg.length" flex="~ wrap justify-center gap-2" mt-2>
            <span v-for="(m, mi) in bigMsg" :key="m" class="cc-chip msg-in"
                  :style="{ '--stagger': Math.min(mi, 6) }" text-16px py-1 px-4>✚ {{ m }}</span>
          </div>
        </section>
      </TransitionGroup>
      <div v-if="!gs.groups.length" text-18px class="idle-hint" style="color: var(--cc-text-3)">
        暂无叫号 · 请留意播报
      </div>

      <!-- 最多 2 个历史组:缩小形态,FLIP 平移 -->
      <TransitionGroup v-if="historyGroups.length" name="hist"
                       tag="div" flex="~ col items-center gap-2" mt-1>
        <div v-for="g in historyGroups" :key="g.id" class="glass-card"
             px-6 py-2 flex="~ items-center gap-4 wrap" text-14px max-w-90vw>
          <span style="color: var(--cc-text-3)">{{ g.calls[0].teacher_name }} · {{ g.calls[0].office }}</span>
          <span font-600>{{ g.calls.map(c => c.student_name).join('、') }}</span>
          <span v-if="g.calls[0].message" class="cc-chip" text-12px>✚ {{ g.calls[0].message }}</span>
        </div>
      </TransitionGroup>
    </main>

    <!-- 走马灯(逐人条目不变) -->
    <footer h-56px flex="~ items-center" overflow-hidden px-10
            style="border-top: 1px solid var(--cc-border)">
      <div class="marquee" flex="~ gap-8" text-15px whitespace-nowrap>
        <span v-for="c in marquee" :key="c.id">
          <b>{{ c.student_name }}</b>
          <span style="color: var(--cc-text-3)">{{ c.created_at.slice(11, 16) }}</span>
        </span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.hero-enter-active { transition: all var(--cc-dur-slow) var(--cc-ease-overshoot); }
.hero-enter-from { opacity: 0; transform: translateY(48px) scale(0.94); }
.hero-leave-active { transition: all var(--cc-dur-fast) ease; position: absolute; }
.hero-leave-to { opacity: 0; }

/* 当前组卡:6s 呼吸光晕(叠加玻璃卡原有投影) */
.breathe { animation: breathe 6s ease-in-out infinite; }
@keyframes breathe {
  0%, 100% { box-shadow: var(--cc-shadow-1), var(--cc-edge-glow), 0 0 20px 0 var(--cc-theme-40); }
  50% { box-shadow: var(--cc-shadow-1), var(--cc-edge-glow), 0 0 28px 6px var(--cc-theme-40); }
}

/* Task-22:hero 卡背景光泽横扫 —— ::after 渐变亮带每 2.8s 掠过一次 */
.hero-card { position: relative; overflow: hidden; }
.hero-card::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(115deg,
    transparent 42%, rgb(255 255 255 / 7%) 46.5%, rgb(255 255 255 / 18%) 50%,
    rgb(255 255 255 / 7%) 53.5%, transparent 58%);
  transform: translateX(-130%);
  animation: sheen 2.8s var(--cc-ease-smooth) 1.4s infinite;
  pointer-events: none;
}
@keyframes sheen {
  0% { transform: translateX(-130%); }
  55%, 100% { transform: translateX(130%); }
}

/* 师/办公室行:字距由 .3em 收拢落定 + 淡入 */
.settle {
  animation: settle var(--cc-dur-slow) var(--cc-ease-smooth) backwards;
}
@keyframes settle {
  from { opacity: 0; letter-spacing: .3em; }
  to { opacity: 1; letter-spacing: normal; }
}

/* 消息 chips:名字入场后(300ms 基线)再上浮弹入 */
.msg-in {
  animation: msg-in var(--cc-dur-cozy) var(--cc-ease-overshoot) backwards;
  animation-delay: calc(300ms + var(--stagger, 0) * 50ms);
}
@keyframes msg-in {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: none; }
}

/* 时钟冒号:1s 脉冲(透明度 + 轻微放大) */
.colon { display: inline-block; animation: colon-pulse 1s var(--cc-ease-smooth) infinite; }
@keyframes colon-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .35; transform: scale(1.18); }
}

/* 暂无叫号:3s 呼吸明暗 */
.idle-hint { animation: idle-breathe 3s ease-in-out infinite; }
@keyframes idle-breathe {
  0%, 100% { opacity: .5; }
  50% { opacity: 1; }
}

/* 名字块:blur-in + 缩放弹入,逐块 40ms 阶梯。
   fill 用 backwards 而非 both:结束后不驻留 keyframe 终态,否则动画帧
   会压过后续 name-leave/name-move 的 transition(动画优先级高于过渡)。 */
.name-blk {
  animation: name-in var(--cc-dur-name) var(--cc-ease-overshoot) backwards;
  animation-delay: calc(var(--stagger, 0) * 40ms);
}
@keyframes name-in {
  from { opacity: 0; filter: blur(10px); transform: scale(0.85); }
  to { opacity: 1; filter: blur(0); transform: scale(1); }
}
.name-enter-active { transition: all var(--cc-dur-fast) ease; }
.name-leave-active { transition: all var(--cc-dur-fast) ease; }
.name-leave-to { opacity: 0; transform: scale(0.8); }
.name-move { transition: transform var(--cc-dur-cozy) var(--cc-ease-smooth); }

/* 字号自适应(1/2-3/4-6/7+ 人) */
.names { font-weight: 700; line-height: 1.1; }
.names-1 { font-size: 12vw; }
.names-2 { font-size: 8vw; }
.names-3 { font-size: 6vw; }
.names-4 { font-size: 4.5vw; }

/* 历史组栈 FLIP */
.hist-move { transition: transform var(--cc-dur-cozy) var(--cc-ease-smooth); }
.hist-enter-active { transition: all var(--cc-dur-cozy) var(--cc-ease-smooth); }
.hist-enter-from { opacity: 0; transform: translateY(12px); }
.hist-leave-active { transition: all var(--cc-dur-fast) ease; position: absolute; }
.hist-leave-to { opacity: 0; }

.marquee { animation: scroll 24s linear infinite; }
/* 老师查历史时悬停暂停 */
.marquee:hover { animation-play-state: paused; }
@keyframes scroll {
  from { transform: translateX(100vw); }
  to { transform: translateX(-100%); }
}

@media (prefers-reduced-motion: reduce) {
  .breathe, .name-blk, .colon, .idle-hint, .settle, .msg-in,
  .hero-card::after { animation: none; }
}
</style>
