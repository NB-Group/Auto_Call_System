<script setup lang="ts">
// Task-21 自绘标题栏:窗口 frameless 后由前端补一块全局顶栏。
// 拖拽:pywebview 注入的 customize.js 会让命中 .pywebview-drag-region
// 选择器(自 target 向上冒泡匹配)的 mousedown 进入拖窗流程 —— 整条栏
// 挂该 class 即为拖拽区;右侧按钮 @mousedown.stop 截断冒泡,可点不拖。
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDark } from '../composables/useDark'

const route = useRoute()
const { isDark, toggleDark } = useDark()
const minimize = () => (window as any).pywebview?.api?.minimize?.()
const quit = () => (window as any).pywebview?.api?.quit?.()

const SUBTITLES: Record<string, string> = {
  '/login': '老师登录',
  '/teacher': '教师端',
  '/admin': '管理端',
  '/server': '服务器端',
  '/snippets': '短语管理',
  '/profile': '个人资料',
}
const subtitle = computed(() => SUBTITLES[route.path] ?? '')
</script>

<template>
  <header class="title-bar pywebview-drag-region" fixed top-0 left-0 right-0 z-40
         h-40px flex="~ items-center" px-3 select-none>
    <div flex="~ items-center gap-2" min-w-0 mr-3>
      <!-- Task-22:应用图标(与 favicon.svg / assets/icon.ico 同源的铃铛) -->
      <span class="brand-icon">
        <svg width="17" height="17" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="ccBrandG" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="hsl(195 100% 55%)" />
              <stop offset="1" stop-color="hsl(210 90% 45%)" />
            </linearGradient>
          </defs>
          <rect width="64" height="64" rx="14" fill="url(#ccBrandG)" />
          <ellipse cx="22" cy="16" rx="26" ry="20" fill="#fff" opacity=".12" />
          <g fill="#fff">
            <circle cx="32" cy="12.5" r="2.6" />
            <path d="M32 15.5a10.5 10.5 0 0 1 10.5 10.5v6.5l2.6 5.5H18.9l2.6-5.5v-6.5A10.5 10.5 0 0 1 32 15.5z" />
            <rect x="17" y="37" width="30" height="4.6" rx="2.3" />
            <circle cx="32" cy="44.8" r="3.6" />
          </g>
          <g stroke="#fff" stroke-opacity=".7" stroke-width="2.4" stroke-linecap="round" fill="none">
            <path d="M17.1 18.6A20 20 0 0 0 17.1 45.4" />
            <path d="M13.4 15.3A25 25 0 0 0 13.4 48.7" />
            <path d="M46.9 18.6A20 20 0 0 1 46.9 45.4" />
            <path d="M50.6 15.3A25 25 0 0 1 50.6 48.7" />
          </g>
        </svg>
      </span>
      <b text-14px whitespace-nowrap>叫号中心</b>
      <span v-if="subtitle" text-12px truncate style="color: var(--cc-text-3)">{{ subtitle }}</span>
    </div>
    <span flex-1 />
    <!-- 方法引用绑定:click 事件作 toggleDark(ev) 首参 → 圆形揭示以按钮为圆心 -->
    <button class="win-btn" title="切换主题" @mousedown.stop @click="toggleDark">
      {{ isDark ? '☀️' : '🌙' }}
    </button>
    <button class="win-btn" title="最小化" @mousedown.stop @click="minimize">─</button>
    <button class="win-btn win-btn-close" title="关闭" @mousedown.stop @click="quit">×</button>
  </header>
</template>

<style scoped>
.title-bar {
  background: var(--cc-content);
  backdrop-filter: var(--cc-glass-1);
  -webkit-backdrop-filter: var(--cc-glass-1);
  border-bottom: 1px solid var(--cc-border);
}
.win-btn {
  width: 34px; height: 28px;
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: var(--cc-radius-half);
  background: transparent; color: var(--cc-text-2);
  font-size: 14px; line-height: 1; cursor: pointer;
  transition: background var(--cc-dur-fast) var(--cc-ease-smooth),
    color var(--cc-dur-fast) var(--cc-ease-smooth),
    transform var(--cc-dur-fast) var(--cc-ease-overshoot);
}
.win-btn:hover { background: var(--cc-fill-2); transform: scale(1.08); }
.win-btn-close:hover { background: #e8112d; color: #fff; }
.win-btn:active { transform: scale(0.94); }

/* Task-22:应用图标 hover 轻微摇摆 */
.brand-icon { display: inline-flex; align-items: center; }
.brand-icon svg { display: block; }
.brand-icon:hover svg { animation: wobble var(--cc-dur-slow) var(--cc-ease-smooth); }
@keyframes wobble {
  0% { transform: rotate(0deg); }
  25% { transform: rotate(-10deg) scale(1.1); }
  55% { transform: rotate(7deg); }
  80% { transform: rotate(-3deg); }
  100% { transform: rotate(0deg); }
}
@media (prefers-reduced-motion: reduce) {
  .brand-icon:hover svg { animation: none; }
}
</style>
