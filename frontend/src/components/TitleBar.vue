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
      <span style="color: var(--cc-theme)">●</span>
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
  transition: background var(--cc-dur-fast) var(--cc-ease-smooth);
}
.win-btn:hover { background: var(--cc-fill-2); }
.win-btn-close:hover { background: #e8112d; color: #fff; }
</style>
