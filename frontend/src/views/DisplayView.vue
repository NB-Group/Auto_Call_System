<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type CallItem } from '../api'
import { connectWS } from '../ws'
import ClassPicker from '../components/ClassPicker.vue'
import { useDark } from '../composables/useDark'

const { forceDark } = useDark()
const classId = Number(localStorage.getItem('cc_class')) || null
const className = ref(localStorage.getItem('cc_class_name') || '')
const picked = ref(classId !== null)
const cards = ref<CallItem[]>([])
const marquee = ref<CallItem[]>([])
const online = ref(false)
const clock = ref('')
let ws: ReturnType<typeof connectWS> | null = null
let timer: number | undefined

function tick() {
  clock.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function onPicked(id: number, name: string) {
  localStorage.setItem('cc_class', String(id))
  localStorage.setItem('cc_class_name', name)
  className.value = name
  picked.value = true
  ws?.subscribe(id)
}

onMounted(() => {
  forceDark()
  tick(); timer = window.setInterval(tick, 1000)
  ws = connectWS({
    classId: classId ?? undefined,
    onStatus: v => (online.value = v),
    onCall: (call) => {
      cards.value = [call, ...cards.value].slice(0, 3)
      marquee.value = [call, ...marquee.value].slice(0, 30)
      window.pywebview?.api?.speak?.(call.announce)
    },
    onRetract: (id) => {
      cards.value = cards.value.filter(c => c.id !== id)
      marquee.value = marquee.value.filter(c => c.id !== id)
    },
  })
})
onUnmounted(() => { ws?.close(); clearInterval(timer) })

// filter(Boolean):message 为空('' .split(',') 得 [''])时不渲染空 chip
const bigMsg = computed(() => (cards.value[0]?.message || '').split(',').filter(Boolean))
</script>

<template>
  <div v-if="!picked"><ClassPicker @picked="onPicked" /></div>
  <div v-else h-full flex="~ col" overflow-hidden pos-relative>
    <!-- 顶栏:班级+时钟+状态 -->
    <header flex="~ items-center" justify-between px-10 py-6>
      <span text-20px font-600>{{ className }}</span>
      <span text-20px font-300 style="font-variant-numeric: tabular-nums">{{ clock }}</span>
      <span text-13px :style="{ color: online ? 'var(--cc-theme)' : 'var(--cc-text-4)' }">
        {{ online ? '● 已连接' : '○ 连接中断,自动重连中…' }}
      </span>
    </header>

    <!-- 当前叫号 hero 卡 -->
    <main flex-1 flex="~ col items-center justify-center" gap-6 px-10>
      <TransitionGroup name="hero">
        <section v-if="cards[0]" :key="cards[0].id" class="glass-card"
                 min-w-720px px-16 py-12 flex="~ col items-center" gap-4>
          <div text-16px style="color: var(--cc-text-3)">请以下同学到</div>
          <div text="12vw leading-1" font-700>{{ cards[0].student_name }}</div>
          <div text-24px>{{ cards[0].teacher_name }} · {{ cards[0].office }}</div>
          <div v-if="bigMsg.length" flex="~ wrap justify-center gap-2" mt-2>
            <span v-for="m in bigMsg" :key="m" class="cc-chip" text-16px py-1 px-4>✚ {{ m }}</span>
          </div>
        </section>
      </TransitionGroup>
      <div v-if="!cards.length" text-18px style="color: var(--cc-text-3)">
        暂无叫号 · 请留意播报
      </div>
    </main>

    <!-- 走马灯 -->
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
.hero-enter-from { opacity: 0; transform: translateY(40px) scale(0.96); }
.hero-leave-active { transition: all var(--cc-dur-fast) ease; position: absolute; }
.hero-leave-to { opacity: 0; }
.marquee { animation: scroll 24s linear infinite; }
@keyframes scroll {
  from { transform: translateX(100vw); }
  to { transform: translateX(-100%); }
}
</style>
