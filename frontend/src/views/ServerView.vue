<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, token } from '../api'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

const needsAdmin = ref<boolean | null>(null)
const info = ref<{ version: string; displays: number } | null>(null)
const username = ref(''); const password = ref('')
const repo = ref('NB-Group/Auto_Call_System')
const mirrorsText = ref('')
const { push } = useToast()

async function refresh() {
  needsAdmin.value = null
  const st = await api.bootstrapStatus()
  if (st.needs_admin) { needsAdmin.value = true; return }
  needsAdmin.value = false
  if (token.get()) {
    try { info.value = await api.admin.serverInfo() } catch { info.value = null }
  }
}
onMounted(async () => {
  await refresh()
  // 浏览器开发模式下 pywebview 未注入,可选链直接跳过
  const cfg = await (window as any).pywebview?.api?.get_update_config?.()
  if (cfg) {
    const c = JSON.parse(cfg)
    repo.value = c.repo
    mirrorsText.value = (c.mirrors as string[]).join('\n')
  }
})

async function saveUpdateCfg() {
  const mirrors = mirrorsText.value.split('\n').map(s => s.trim()).filter(Boolean)
  await (window as any).pywebview?.api?.set_update_config?.(
    repo.value.trim(), JSON.stringify(mirrors))
  push('更新设置已保存')
}

async function createAdmin() {
  try {
    const r = await api.bootstrapAdmin(username.value.trim(), password.value)
    token.set(r.token); push('管理员已创建')
    await refresh()
  } catch (e: any) { push(`创建失败:${e.message}`) }
}
</script>

<template>
  <div max-w-640px mx-auto px-6 py-10>
    <!-- 首次:创建管理员 -->
    <form v-if="needsAdmin" class="glass-card" p-8 flex="~ col gap-4" @submit.prevent="createAdmin">
      <h1 text-22px font-600 m-0>初始化服务器</h1>
      <p text-13px m-0 style="color: var(--cc-text-3)">首次使用,请创建管理员账号</p>
      <input v-model="username" class="cc-input" placeholder="管理员用户名">
      <input v-model="password" class="cc-input" type="password" placeholder="密码(至少 6 位)">
      <button class="cc-btn cc-btn-primary">创建</button>
    </form>

    <!-- 状态页 -->
    <div v-else-if="needsAdmin === false" class="glass-card" p-8 flex="~ col gap-4">
      <h1 text-22px font-600 m-0>服务器运行中</h1>
      <div flex="~ justify-between"><span style="color:var(--cc-text-3)">版本</span><b>v{{ info?.version ?? '—' }}</b></div>
      <div flex="~ justify-between"><span style="color:var(--cc-text-3)">在线显示端</span><b>{{ info?.displays ?? '—' }}</b></div>
      <p text-13px m-0 style="color: var(--cc-text-3)">
        老师端与显示端在局域网内自动发现本服务器,无需配置。
      </p>
      <a href="#/login" class="cc-btn cc-btn-primary" style="text-decoration:none; text-align:center">
        进入管理后台
      </a>
    </div>
    <div v-if="needsAdmin === false" class="glass-card" p-8 mt-4 flex="~ col gap-3">
      <h2 text-16px font-600 m-0>更新设置</h2>
      <label flex="~ col gap-1" text-13px>
        GitHub 仓库(owner/name)
        <input v-model="repo" class="cc-input" placeholder="NB-Group/Auto_Call_System">
      </label>
      <label flex="~ col gap-1" text-13px>
        镜像源前缀(每行一个,留空行 = 直连)
        <textarea v-model="mirrorsText" class="cc-input" rows-4 />
      </label>
      <button class="cc-btn cc-btn-primary" @click="saveUpdateCfg">保存</button>
    </div>
    <Toasts />
  </div>
</template>
