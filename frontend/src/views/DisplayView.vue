<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type CallItem } from '../api'
import { connectWS } from '../ws'
import ClassPicker from '../components/ClassPicker.vue'
import { useDark } from '../composables/useDark'
import { GROUP_WINDOW_MS, closeExpired, groupAnnounce, initGroups, onCall as onGroupCallRaw, onRetract, type GroupsState } from '../callGroups'
import { autoCollapse, initDisplayMode, onGroupCall as onModeCall, onGroupsEmpty, toggleManual, type DisplayModeState } from '../displayMode'

const { forceDark } = useDark()
const classId = Number(localStorage.getItem('cc_class')) || null
const className = ref(localStorage.getItem('cc_class_name') || '')
const picked = ref(classId !== null)
const gs = ref<GroupsState>(initGroups())
const marquee = ref<CallItem[]>([])
const online = ref(false)
const clock = ref('')
// Task-23 小窗形态:右下角常驻,来号自动全屏,末组结束 12s 自动收回
const dm = ref<DisplayModeState>(initDisplayMode())
// C2 语音播报开关:默认开,localStorage 持久化('0'=关)
const voiceOn = ref(localStorage.getItem('cc_voice') !== '0')
// 一批一念:已播报过的组 id(只念一遍的闸门);仅存栈内组,栈深 3 无泄漏
const spokenGroups = new Set<number>()
let ws: ReturnType<typeof connectWS> | null = null
let timer: number | undefined
let sweepTimer: number | undefined

function toggleVoice() {
  voiceOn.value = !voiceOn.value
  localStorage.setItem('cc_voice', voiceOn.value ? '1' : '0')
}

/** 形态状态唯一出口:expanded 变化才调 bridge(浏览器环境可选链无副作用) */
function syncMode(next: DisplayModeState) {
  if (next.expanded !== dm.value.expanded)
    window.pywebview?.api?.set_display_mode?.(next.expanded ? 'expand' : 'collapse')
  dm.value = next
}

/** 组栈变化后补锚点:清空瞬间记录时间戳(autoCollapse 的 12s 起点) */
function anchorEmpty() {
  if (gs.value.groups.length === 0 && dm.value.lastGroupClosedAt === null)
    syncMode(onGroupsEmpty(dm.value, Date.now()))
}

function tick() {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  clock.value = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  // 1s 顺带驱动自动收起判定(纯函数幂等,expanded 已 false 时零开销)
  syncMode(autoCollapse(dm.value, Date.now()))
}

function connect(sub?: number) {
  ws = connectWS({
    classId: sub,
    onStatus: v => (online.value = v),
    // 突发聚合:老师端循环 N 次 call → 服务端连发 N 条广播,同师同消息 1.2s 内聚一卡
    onCall: (call) => {
      gs.value = onGroupCallRaw(gs.value, call, Date.now())
      // 来号即展开(冷却期内新组也取消收起计时);卡面立即可见,语音在窗关时才念
      syncMode(onModeCall(dm.value))
      // 兜底清窗旗 + 一批一念:窗口落定(末次叫号后 1.2s)整组合成一条播报,
      // 只念一遍(此前逐人念、TTS 再×2 遍,慢 —— 用户拍板一批一念)。
      // 计时器随每次叫号重排:不续叫就到此点,所有到期组在此落定。
      clearTimeout(sweepTimer)
      sweepTimer = window.setTimeout(() => {
        gs.value = closeExpired(gs.value, Date.now())
        // 新关组播报:按叫号先后念(栈新在前,倒序=时间正序);spokenGroups 保证每组只念一次
        for (const g of [...gs.value.groups].reverse()) {
          if (g.closed && !spokenGroups.has(g.id)) {
            spokenGroups.add(g.id)
            if (voiceOn.value) window.pywebview?.api?.speak?.(groupAnnounce(g))
          }
        }
        for (const id of [...spokenGroups])
          if (!gs.value.groups.some(g => g.id === id)) spokenGroups.delete(id)
        anchorEmpty()
      }, GROUP_WINDOW_MS + 100)
      marquee.value = [call, ...marquee.value].slice(0, 30)
    },
    onRetract: (id) => {
      gs.value = onRetract(gs.value, id)
      marquee.value = marquee.value.filter(c => c.id !== id)
      anchorEmpty()
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

const quit = () => window.pywebview?.api?.quit?.()

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
      // id 仍有效时,以服务器最新班名回填(换库/改名后别再亮旧班牌)
      const fresh = list.find(c => c.id === classId)
      if (fresh && fresh.name !== className.value) {
        className.value = fresh.name
        localStorage.setItem('cc_class_name', fresh.name)
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
// 小窗"今日已叫 N 人":走马灯栈长度(撤销已被过滤,即当前有效人数)
const calledCount = computed(() => marquee.value.length)
</script>

<template>
  <div v-if="!picked" h-full overflow-y-auto><ClassPicker @picked="onPicked" /></div>
  <!-- Task-23:小窗(收起)↔ 全屏(展开)两形态;右下角原点缩放切换,
       out-in 让旧形态先收进角落、新形态再从角落长出来 -->
  <div v-else h-full overflow-hidden pos-relative flex="~">
    <Transition name="mode" mode="out-in" appear>

      <!-- 小窗形态:400×250 常驻卡(真实窗口内恰好满幅;浏览器回退居中) -->
      <div v-if="!dm.expanded" key="corner" class="glass-card"
           w-400px h-250px m-auto flex="~ col" overflow-hidden select-none>
        <!-- 迷你拖拽条:壳 customize.js 令 .pywebview-drag-region 可拖窗 -->
        <div class="corner-strip pywebview-drag-region" flex="~ items-center gap-2" px-10px>
          <span text-11px font-600 style="color: var(--cc-text-3)">叫号中心</span>
          <span text-11px :style="{ color: online ? 'var(--cc-theme)' : 'var(--cc-text-4)' }">
            {{ online ? '● 已连接' : '○ 重连中' }}
          </span>
          <span flex-1 />
          <button class="corner-x" title="关闭" @mousedown.stop @click="quit">×</button>
        </div>
        <!-- 主体:班级 + 大时钟 + 叫号概览 -->
        <div flex-1 flex="~ col items-center justify-center" gap-4px overflow-hidden>
          <div text-20px font-600 truncate max-w-360px>{{ className }}</div>
          <div text-40px font-300 leading-none style="font-variant-numeric: tabular-nums"><span
            v-for="(seg, i) in clock.split(':')" :key="i"><span v-if="i" class="colon">:</span>{{ seg }}</span></div>
          <div v-if="gs.groups.length" text-13px truncate max-w-360px
               style="color: var(--cc-theme)">
            {{ hero!.calls.map(c => c.student_name).join('、') }}
          </div>
          <div v-else text-14px class="idle-hint" style="color: var(--cc-text-3)">暂无叫号 · 请留意播报</div>
        </div>
        <!-- 底行:一键全屏 + 播报开关 + 今日计数 -->
        <div flex="~ items-center justify-between" px-14px pb-10px>
          <div flex="~ items-center gap-6px">
            <button class="cc-btn" text-13px py-1 px-3
                    @mousedown.stop @click="syncMode(toggleManual(dm))">⛶ 全屏</button>
            <button class="cc-btn" text-13px py-1 px-3
                    :title="voiceOn ? '关闭语音播报' : '开启语音播报'"
                    @mousedown.stop @click="toggleVoice">
              <span :key="String(voiceOn)" class="voice-ico">{{ voiceOn ? '🔊' : '🔇' }}</span>
              播报 {{ voiceOn ? '开' : '关' }}
            </button>
          </div>
          <span text-12px style="color: var(--cc-text-3)">今日已叫 {{ calledCount }} 人</span>
        </div>
      </div>

      <!-- 展开形态:原 hero/历史/走马灯全屏 UI。
           fixed inset-0:脱离祖先高度链(App.vue 无栏路由的包裹 div 高度 auto,
           h-full 百分比会塌陷成内容高),直接锚定视口全幅,任何窗口尺寸都撑满 -->
      <div v-else key="full" fixed inset-0 flex="~ col" overflow-hidden>
        <!-- 悬浮控件(kiosk 顶右):播报开关 + 退出钮 -->
        <div fixed top-16px right-16px z-30 flex="~ items-center gap-8px">
          <button class="glass-pop voice-fs" text-14px py-2 px-4
                  :title="voiceOn ? '关闭语音播报' : '开启语音播报'"
                  @mousedown.stop @click="toggleVoice">
            <span :key="String(voiceOn)" class="voice-ico">{{ voiceOn ? '🔊' : '🔇' }}</span>
            播报 {{ voiceOn ? '开' : '关' }}
          </button>
          <button class="glass-pop exit-fs" text-14px py-2 px-4
                  @mousedown.stop @click="syncMode(toggleManual(dm))">⤡ 退出全屏</button>
        </div>
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
    </Transition>
  </div>
</template>

<style scoped>
/* ===== Task-23:小窗↔全屏形态切换(右下角原点缩放,像小窗长成全屏)===== */
.mode-enter-active, .mode-leave-active {
  transition: opacity var(--cc-dur-slow) var(--cc-ease-smooth),
    transform var(--cc-dur-slow) var(--cc-ease-overshoot);
  transform-origin: bottom right;
}
.mode-enter-from, .mode-leave-to { opacity: 0; transform: scale(0.34); }

/* 小窗迷你拖拽条 */
.corner-strip {
  height: 28px;
  flex: none;
  font-size: 11px;
  border-bottom: 1px solid var(--cc-border);
  user-select: none;
  cursor: default;
}
.corner-x {
  width: 26px; height: 22px;
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: var(--cc-radius-half);
  background: transparent; color: var(--cc-text-2);
  font-size: 14px; line-height: 1; cursor: pointer;
  transition: background var(--cc-dur-fast) var(--cc-ease-smooth);
}
.corner-x:hover { background: #e8112d; color: #fff; }

/* 全屏态悬浮退出钮:rest 低调半透明,hover 点亮 */
.exit-fs {
  border: 1px solid var(--cc-border);
  color: var(--cc-text-2);
  cursor: pointer;
  opacity: 0.55;
  transition: opacity var(--cc-dur-fast) var(--cc-ease-smooth),
    transform var(--cc-dur-fast) var(--cc-ease-overshoot),
    box-shadow var(--cc-dur-fast) var(--cc-ease-smooth);
}
.exit-fs:hover { opacity: 1; transform: scale(1.05); box-shadow: var(--cc-shadow-2); }

/* 播报开关(小窗+全屏共用):图标每次切换重挂载弹跳一下(:key 翻转) */
.voice-fs {
  border: 1px solid var(--cc-border);
  color: var(--cc-text-2);
  cursor: pointer;
  transition: opacity var(--cc-dur-fast) var(--cc-ease-smooth),
    transform var(--cc-dur-fast) var(--cc-ease-overshoot);
}
.voice-fs:hover { transform: scale(1.05); }
.voice-ico {
  display: inline-block;
  animation: voice-pop var(--cc-dur-cozy) var(--cc-ease-overshoot);
}
@keyframes voice-pop {
  from { opacity: 0; transform: scale(0.4) rotate(-14deg); }
  to { opacity: 1; transform: none; }
}

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
  .voice-ico, .hero-card::after { animation: none; }
  .mode-enter-active, .mode-leave-active { transition: none; }
}
</style>
