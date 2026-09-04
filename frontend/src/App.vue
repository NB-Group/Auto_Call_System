<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDark } from './composables/useDark'
import TitleBar from './components/TitleBar.vue'

const { initTheme } = useDark()
const route = useRoute()
const update = ref<{ version: string; notes: string } | null>(null)
// 真重启(壳 ≥0.1.7 先拉新进程再退);旧壳无 restart 时退回纯退出
const restart = () => {
  const api = (window as any).pywebview?.api
  if (api?.restart) api.restart()
  else api?.quit?.()
}
// 显示端(教室大屏)fullscreen 无边栏,不得被 40px 标题栏挤下去
const showBar = computed(() => route.path !== '/display')

onMounted(() => {
  initTheme()
  window.addEventListener('cc-update', (ev) => {
    update.value = (ev as CustomEvent).detail
  })
})
</script>

<template>
  <TitleBar v-if="showBar" />
  <!-- 有栏路由:内容整体下移 40px,滚动收在本容器(body 不滚,Toasts/横幅 fixed 不受影响)。
       h-full 无条件挂:无栏路由(/display)也保住 #app→view 的高度链 —— 否则包裹层
       高度 auto,DisplayView 根的 h-full 百分比塌陷,小窗在浏览器回退时无法垂直居中 -->
  <div h-full :class="showBar ? 'app-frame' : ''">
    <!-- 路由切换:淡入淡出 + 轻微上浮(out-in 避免新旧页叠滚) -->
    <router-view v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </router-view>
  </div>
  <!-- left-1/2 translate-x--1/2 含 '/',SFC 解析器拒绝出现在属姓名中,改显式 style(同 Toasts) -->
  <!-- 有栏时 top 让出 40px 标题栏,避免横幅压在栏上 -->
  <div v-if="update" class="glass-pop" fixed z-50 text-14px
       :style="{ top: showBar ? '56px' : '16px', left: '50%', transform: 'translateX(-50%)' }"
       px-5 py-3 flex="~ items-center gap-3">
    <span>新版本 v{{ update.version }} 已就绪,重启后生效</span>
    <button class="cc-btn cc-btn-primary" py-1 @click="restart">立即重启</button>
  </div>
</template>

<style scoped>
.app-frame {
  height: 100%;
  padding-top: 40px;
  box-sizing: border-box;
  overflow-y: auto;
}

/* 路由切换:淡入淡出 + 上浮 + 轻微缩放(out-in 避免新旧页叠滚) */
.page-enter-active {
  transition: opacity var(--cc-dur-page-in) var(--cc-ease-smooth),
    transform var(--cc-dur-page-in) var(--cc-ease-smooth);
}
.page-leave-active {
  transition: opacity var(--cc-dur-page-out) ease,
    transform var(--cc-dur-page-out) ease;
}
.page-enter-from { opacity: 0; transform: translateY(10px) scale(0.98); }
.page-leave-to { opacity: 0; transform: scale(0.985); }
</style>
