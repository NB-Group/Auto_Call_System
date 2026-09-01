<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type MeInfo } from '../api'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

const me = ref<MeInfo | null>(null)
const { push } = useToast()
onMounted(async () => { me.value = await api.me() })

async function save() {
  if (!me.value) return
  me.value = await api.updateMe({
    display_name: me.value.display_name, office: me.value.office,
    default_template: me.value.default_template,
  })
  push('已保存')
}
</script>

<template>
  <div v-if="me" max-w-560px mx-auto px-6 py-6>
    <div flex="~ items-center justify-between" mb-4>
      <h1 text-20px font-600 m-0>我的资料</h1>
      <a href="#/teacher" class="cc-btn" style="text-decoration:none">返回</a>
    </div>
    <form class="glass-card" p-6 flex="~ col gap-4" @submit.prevent="save">
      <label flex="~ col gap-1" text-13px>
        称呼(播报用)
        <input v-model="me.display_name" class="cc-input" placeholder="郑老师">
      </label>
      <label flex="~ col gap-1" text-13px>
        办公室位置
        <input v-model="me.office" class="cc-input" placeholder="203办公室">
      </label>
      <label flex="~ col gap-1" text-13px>
        播报模板(可用 {student} {teacher} {office})
        <input v-model="me.default_template" class="cc-input">
      </label>
      <div text-12px style="color: var(--cc-text-3)">
        预览:请梁皓文同学到{{ me.display_name || '…' }}{{ me.office || '…' }}
      </div>
      <button class="cc-btn cc-btn-primary" type="submit">保存</button>
    </form>
    <Toasts />
  </div>
</template>
